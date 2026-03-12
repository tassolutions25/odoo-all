# -*- coding: utf-8 -*-
import logging
from datetime import datetime, timedelta
import pytz
from odoo import models, fields, api, _
from odoo.exceptions import UserError

# --- SAFE IMPORT ---
try:
    import pymssql
except ImportError:
    pymssql = None

_logger = logging.getLogger(__name__)

class BiotimeDBManager(models.Model):
    _name = 'biotime.db.manager'
    _description = 'BioTime Direct Database Synchronizer (MSSQL)'

    @api.model
    def _get_db_connection(self):
        """Establish connection to BioTime MS SQL Database"""
        if not pymssql:
            raise UserError(_("The 'pymssql' Python library is not installed. Please run: pip install pymssql"))

        ICP = self.env['ir.config_parameter'].sudo()
        try:
            # Fetch credentials from Settings
            db_host = ICP.get_param('biotime.db_host')
            db_port = ICP.get_param('biotime.db_port')
            db_name = ICP.get_param('biotime.db_name')
            db_user = ICP.get_param('biotime.db_user')
            db_password = ICP.get_param('biotime.db_password')

            if not all([db_host, db_name, db_user, db_password]):
                raise UserError("Database credentials are incomplete in Settings.")

            conn = pymssql.connect(
                server=db_host,
                port=db_port,
                user=db_user,
                password=db_password,
                database=db_name,
                as_dict=False
            )
            return conn
        except Exception as e:
            raise UserError(f"MSSQL Connection Failed: {e}")

    @api.model
    def sync_attendance_db_daily_summary(self, start_date_str, end_date_str):
        """
        Connects to MSSQL DB and gets First In / Last Out per day.
        Strictly handles Miss-Outs by closing previous open records with 0 duration.
        """
        _logger.info("🚀 Starting Direct DB Sync (Strict Miss-Out Mode)...")
        
        ICP = self.env['ir.config_parameter'].sudo()
        tz_name = ICP.get_param('biotime.timezone', 'Africa/Addis_Ababa')
        
        try:
            local_tz = pytz.timezone(tz_name)
        except:
            local_tz = pytz.UTC

        # Parse Dates
        start_dt = fields.Datetime.from_string(start_date_str)
        end_dt = fields.Datetime.from_string(end_date_str)

        conn = None
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()

            # MSSQL Query: Get First and Last punch per day
            query = """
                SELECT
                    emp_code,
                    CAST(punch_time AS DATE) as punch_day,
                    MIN(punch_time) as first_punch,
                    MAX(punch_time) as last_punch,
                    COUNT(id) as total_punches
                FROM
                    iclock_transaction
                WHERE
                    punch_time >= %s AND punch_time <= %s
                GROUP BY
                    emp_code, CAST(punch_time AS DATE)
                ORDER BY
                    punch_day ASC, emp_code ASC;
            """

            _logger.info(f"Executing MSSQL Query from {start_dt} to {end_dt}")
            cursor.execute(query, (start_dt, end_dt))
            rows = cursor.fetchall()
            
            cursor.close()
            conn.close()

            total_created = 0
            total_updated = 0
            total_missouts = 0
            missing_employees = set()
            
            # Cache Employees
            all_codes = list(set([str(r[0]).strip() for r in rows if r[0]]))
            employees = self.env['hr.employee'].search([('employee_id', 'in', all_codes)])
            emp_map = {e.employee_id: e.id for e in employees}

            processed_count = 0
            
            for row in rows:
                processed_count += 1
                emp_code_raw = row[0]
                if not emp_code_raw: continue
                emp_code = str(emp_code_raw).strip()

                employee_odoo_id = emp_map.get(emp_code)
                if not employee_odoo_id:
                    missing_employees.add(emp_code)
                    continue

                try:
                    first_punch_native = row[2]
                    last_punch_native = row[3]
                    
                    # Localize (Addis) -> UTC -> Naive
                    check_in_local = local_tz.localize(first_punch_native)
                    check_in_utc_aware = check_in_local.astimezone(pytz.UTC)
                    check_in_final = check_in_utc_aware.replace(tzinfo=None)

                    check_out_final = False
                    # Only set check-out if Last Punch is different from First Punch
                    if row[4] > 1 and last_punch_native != first_punch_native:
                        check_out_local = local_tz.localize(last_punch_native)
                        check_out_utc_aware = check_out_local.astimezone(pytz.UTC)
                        check_out_final = check_out_utc_aware.replace(tzinfo=None)

                except Exception as e:
                    _logger.error(f"Time conversion error for {emp_code}: {e}")
                    continue

                # --- 1. STRICT MISS-OUT LOGIC ---
                # Find any open attendance strictly BEFORE today.
                # If found, it means they missed checkout on that previous day.
                # We MUST close it to allow today's record to be created.
                stuck_attendance = self.env['hr.attendance'].search([
                    ('employee_id', '=', employee_odoo_id),
                    ('check_out', '=', False),
                    ('check_in', '<', check_in_final.date()) # Older dates only
                ], limit=1)

                if stuck_attendance:
                    # Close it with 0 duration (CheckOut = CheckIn)
                    # Mark it as 'miss_out' so reports see it correctly
                    stuck_attendance.write({
                        'check_out': stuck_attendance.check_in, 
                        'check_out_method': 'System',
                        'attendance_status': 'miss_out',
                        'miss_out_status_handled': True
                    })
                    total_missouts += 1

                # --- 2. CREATE OR UPDATE CURRENT DAY ---
                # Check for existing record on this exact Check-In time
                existing = self.env['hr.attendance'].search([
                    ('employee_id', '=', employee_odoo_id),
                    ('check_in', '=', check_in_final)
                ], limit=1)

                if not existing:
                    # Double check for ANY record overlapping today to avoid duplicates
                    day_start = check_in_final.replace(hour=0, minute=0, second=0)
                    day_end = check_in_final.replace(hour=23, minute=59, second=59)
                    existing_day = self.env['hr.attendance'].search([
                        ('employee_id', '=', employee_odoo_id),
                        ('check_in', '>=', day_start),
                        ('check_in', '<=', day_end)
                    ], limit=1)
                    if existing_day:
                        existing = existing_day

                if existing:
                    # Update checkout if we have a better one from DB
                    if check_out_final:
                        if not existing.check_out or existing.check_out != check_out_final:
                            existing.write({
                                'check_out': check_out_final,
                                'check_out_method': 'Biometric'
                            })
                            total_updated += 1
                else:
                    # Create New
                    try:
                        vals = {
                            'employee_id': employee_odoo_id,
                            'check_in': check_in_final,
                            'check_in_method': 'Biometric',
                        }
                        if check_out_final:
                            vals['check_out'] = check_out_final
                            vals['check_out_method'] = 'Biometric'
                        else:
                            vals['check_out'] = False 

                        self.env['hr.attendance'].create(vals)
                        total_created += 1
                    except Exception as e:
                        # Log error but CONTINUE the loop
                        _logger.warning(f"Could not create attendance for {emp_code} on {check_in_final}: {e}")
                        continue

                # --- BATCH COMMIT ---
                # Commit every 50 records to prevent 600s Timeout error
                if processed_count % 50 == 0:
                    self.env.cr.commit()

            # Final result message
            msg = f"✅ MSSQL Sync Complete.\n\n" \
                  f"📅 Days Processed: {len(rows)}\n" \
                  f"🆕 Created: {total_created}\n" \
                  f"🔄 Updated: {total_updated}\n" \
                  f"⚠️ Miss-Outs Fixed: {total_missouts}"
            
            if missing_employees:
                sorted_missing = sorted(list(missing_employees))
                display_missing = ", ".join(sorted_missing[:5])
                if len(sorted_missing) > 5:
                    display_missing += f", ... (+{len(sorted_missing)-5} more)"
                msg += f"\n\n❓ IGNORED ({len(missing_employees)}) Unknown IDs: {display_missing}"

            return {"success": True, "message": msg}

        except Exception as e:
            _logger.error(f"MSSQL Sync Error: {e}", exc_info=True)
            if conn: conn.close()
            return {"success": False, "message": f"Timeout/Error: {str(e)}. Some records may have been saved."}

