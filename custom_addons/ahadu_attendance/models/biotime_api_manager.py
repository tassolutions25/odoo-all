# -*- coding: utf-8 -*-
import requests
import logging
from datetime import datetime, timedelta, timezone
import pytz

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)

class BiotimeApiManager(models.Model):
    _name = 'biotime.api.manager'
    _description = 'BioTime Integration Engine'

    @api.model
    def _get_cfg(self):
        p = self.env["ir.config_parameter"].sudo()
        url = p.get_param("biotime.api_url")
        if url:
            url = url.strip().rstrip('/')
            if not url.startswith('http://') and not url.startswith('https://'):
                url = f"http://{url}"

        cfg = {
            "url": url,
            "user": p.get_param("biotime.api_user"),
            "password": p.get_param("biotime.api_password"),
            "timeout": int(p.get_param("biotime.api_timeout", "30")),
            "timezone": p.get_param("biotime.timezone", "Africa/Addis_Ababa"),
        }
        if not all([cfg["url"], cfg["user"], cfg["password"]]):
            return {"error": "BioTime API parameters are missing."}
        return cfg

    @api.model
    def _get_token(self, cfg):
        ICP = self.env["ir.config_parameter"].sudo()
        auth_url = f"{cfg['url']}/jwt-api-token-auth/"
        payload = {"username": cfg["user"], "password": cfg["password"]}
        try:
            r = requests.post(auth_url, json=payload, timeout=cfg["timeout"])
            r.raise_for_status()
            token = r.json().get("token")
            if token:
                ICP.set_param("biotime.jwt_token", token)
                return {"token": token}
            return {"error": "No token returned from BioTime."}
        except Exception as e:
            return {"error": f"Connection Failed: {str(e)}"}

    @api.model
    def sync_employees_to_biotime(self):
        # Dummy method to prevent crashes if clicked
        return {"success": True, "message": "Employee Sync is currently disabled/placeholder."}

    @api.model
    def sync_attendance_from_biotime(self, manual_start=None, manual_end=None):
        """
        Sync attendance data from BioTime with batch processing and progress tracking.
        Implements 500-record batching with intermediate commits to prevent timeouts.
        """
        _logger.info("🔄 Starting BioTime Sync...")
        cfg = self._get_cfg()
        if "error" in cfg: 
            return {"success": False, "message": cfg["error"]}
        
        token_res = self._get_token(cfg)
        if "error" in token_res: 
            return {"success": False, "message": token_res["error"]}
        token = token_res["token"]

        ICP = self.env["ir.config_parameter"].sudo()
        
        # Get timezone
        try:
            bt_tz = pytz.timezone(cfg["timezone"])
        except:
            _logger.warning("Unknown timezone, using UTC")
            bt_tz = pytz.UTC

        # Determine date range
        start_dt = None
        end_dt = datetime.now(timezone.utc)

        if manual_start:
            if isinstance(manual_start, str):
                start_dt = fields.Datetime.from_string(manual_start).replace(tzinfo=timezone.utc)
            else:
                start_dt = manual_start.replace(tzinfo=timezone.utc)
            
            if manual_end:
                if isinstance(manual_end, str):
                    end_dt = fields.Datetime.from_string(manual_end).replace(tzinfo=timezone.utc)
                else:
                    end_dt = manual_end.replace(tzinfo=timezone.utc)
            else:
                end_dt = start_dt + timedelta(days=365)
        else:
            last_sync = ICP.get_param("biotime.last_sync_time")
            if last_sync:
                start_dt = fields.Datetime.from_string(last_sync).replace(tzinfo=timezone.utc)
            else:
                start_dt = datetime.now(timezone.utc) - timedelta(days=1)
            end_dt = datetime.now(timezone.utc)

        url = f"{cfg['url']}/iclock/api/transactions/"
        headers = {"Authorization": f"JWT {token}"}
        
        params = {
            "start_time": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "page_size": 1000
        }

        _logger.info(f"📅 Syncing range: {params['start_time']} to {params['end_time']}")

        # Batch processing variables
        BATCH_SIZE = 500
        attendance_create_batch = []
        attendance_update_batch = []
        
        total_processed = 0
        total_api_records = 0
        batch_count = 0
        latest_seen = start_dt
        
        # Tracking
        missing_employees = set()
        unique_employees = set()

        try:
            # Enable context flag to skip heavy analysis during batch import
            self = self.with_context(skip_analysis_on_import=True)
            hr_attendance_model = self.env['hr.attendance']
            
            while url:
                resp = requests.get(url, headers=headers, params=params, timeout=cfg["timeout"])
                resp.raise_for_status()
                data = resp.json()
                page_items = data.get("data", []) or data.get("results", [])
                
                total_api_records += len(page_items)
                _logger.info(f"📦 Fetched {len(page_items)} records from BioTime API")

                # --- BULK PREFETCH START ---
                # 1. Map Employee Codes to Records
                emp_codes = set(item.get("emp_code") for item in page_items if item.get("emp_code"))
                employees = self.env["hr.employee"].search([("employee_id", "in", list(emp_codes))])
                emp_map = {e.employee_id: e for e in employees} # Code -> Employee Record
                
                # 2. Prefetch Shifts for batch
                if employees:
                    # Get date range for this page (approx)
                    # Use provided start/end keys or strict bounds
                    page_dates = []
                    for item in page_items:
                        pt = item.get("punch_time")
                        if pt:
                             try:
                                 page_dates.append(datetime.fromisoformat(pt.replace(' ', 'T')))
                             except: pass
                    
                    if page_dates:
                        min_date = min(page_dates).replace(hour=0, minute=0, second=0)
                        max_date = max(page_dates).replace(hour=23, minute=59, second=59)

                        # Fetch shifts
                        shifts = self.env['ab.hr.shift.schedule'].search([
                            ('employee_id', 'in', employees.ids),
                            ('state', '=', 'assigned'),
                            ('date_start', '<=', max_date),
                            ('date_end', '>=', min_date)
                        ])
                        
                        shift_cache = {}
                        for s in shifts:
                             if s.employee_id.id not in shift_cache:
                                 shift_cache[s.employee_id.id] = []
                             shift_cache[s.employee_id.id].append(s)
                    else:
                        shift_cache = {}
                else:
                    shift_cache = {}
                # --- BULK PREFETCH END ---

                for item in page_items:
                    emp_code = item.get("emp_code")
                    punch_time_s = item.get("punch_time")
                    
                    if not emp_code or not punch_time_s: 
                        continue

                    # Parse timestamp
                    try:
                        punch_naive_local = datetime.fromisoformat(punch_time_s.replace(' ', 'T'))
                        punch_localized = bt_tz.localize(punch_naive_local)
                        punch_utc_aware = punch_localized.astimezone(pytz.UTC)
                        punch_utc_naive = punch_utc_aware.replace(tzinfo=None)
                    except Exception as e:
                        _logger.warning(f"Failed to parse time '{punch_time_s}': {e}")
                        continue
                    
                    if punch_utc_aware <= start_dt: 
                        continue

                    # Find employee from Map
                    employee = emp_map.get(emp_code.strip())
                    
                    if not employee:
                        missing_employees.add(emp_code)
                        continue
                    
                    unique_employees.add(employee.id)

                    # Check if attendance already exists
                    try:
                        exists = hr_attendance_model.search_count([
                            ('employee_id', '=', employee.id),
                            ('check_in', '=', punch_utc_naive)
                        ])
                        
                        if not exists:
                            # Check for open attendance
                            last_att = hr_attendance_model.search([
                                ('employee_id', '=', employee.id),
                                ('check_out', '=', False)
                            ], order='check_in desc', limit=1)
                             
                            if last_att and punch_utc_naive > last_att.check_in:
                                # This is a check-out
                                attendance_update_batch.append({
                                    'record': last_att,
                                    'vals': {
                                        'check_out': punch_utc_naive,
                                        'check_out_method': 'Biometric',
                                        'biotime_punch_id': item.get('id')
                                    }
                                })
                            else:
                                # --- SMART PAIRING LOGIC (Shift-Aware) ---
                                # Is this a Morning Check-In or Evening Check-Out (Orphan)?
                                
                                is_orphan_out = False
                                
                                # Get Shift Schedule
                                emp_shifts = shift_cache.get(employee.id)
                                target_date = punch_naive_local.date()
                                
                                # Call logic to get start/end
                                exp_start, exp_end, _ = hr_attendance_model._get_expected_schedule(
                                    employee, target_date, bt_tz, employee_shifts=emp_shifts
                                )
                                
                                if exp_start and exp_end:
                                    # Calculate distance
                                    # Convert exp times to UTC for fair comparison with punch_utc_aware
                                    # (Note: _get_expected_schedule returns timezone-aware datetimes matching 'tz' passed)
                                    # punch_utc_aware is aware. exp_start is aware (in bt_tz).
                                    
                                    # Safe compare: convert everything to UTC
                                    exp_start_utc = exp_start.astimezone(pytz.UTC)
                                    exp_end_utc = exp_end.astimezone(pytz.UTC)
                                    
                                    dist_start = abs((punch_utc_aware - exp_start_utc).total_seconds())
                                    dist_end = abs((punch_utc_aware - exp_end_utc).total_seconds())
                                    
                                    # Logic: If significantly closer to End Time than Start Time, assume OUT
                                    # E.g. Punch at 17:00. Start 08:00 (diff 9h), End 17:00 (diff 0h). -> OUT.
                                    # E.g. Punch at 13:00. Start 08:00 (diff 5h), End 17:00 (diff 4h). -> OUT?
                                    # Let's enforce a midpoint buffer? Or simple comparison?
                                    
                                    # Strict Rule: If punch is after midpoint, and NO check-in exists -> Orphan Out
                                    if dist_end < dist_start:
                                        is_orphan_out = True

                                if is_orphan_out:
                                    _logger.info(f"Orphan Check-Out detected for {employee.name} at {punch_utc_naive}")
                                    # Create "Orphan Out" record
                                    attendance_create_batch.append({
                                        'employee_id': employee.id,
                                        'check_in': punch_utc_naive,
                                        'check_out': punch_utc_naive, # Zero Duration
                                        'check_in_method': 'Biometric',
                                        'check_out_method': 'Biometric',
                                        'biotime_punch_id': item.get('id'),
                                        'attendance_status': 'miss_in', # Special status
                                        'worked_hours': 0.0
                                    })
                                else:
                                    # Normal Check-In
                                    attendance_create_batch.append({
                                        'employee_id': employee.id,
                                        'check_in': punch_utc_naive,
                                        'check_in_method': 'Biometric',
                                        'biotime_punch_id': item.get('id')
                                    })
                             
                    except Exception as e:
                        _logger.error(f"Error processing attendance for {emp_code}: {e}")
                        continue

                    if punch_utc_aware > latest_seen: 
                        latest_seen = punch_utc_aware

                    # Process batch when it reaches BATCH_SIZE
                    if len(attendance_create_batch) >= BATCH_SIZE:
                        batch_count += 1
                        _logger.info(f"💾 Processing batch #{batch_count} ({len(attendance_create_batch)} create, {len(attendance_update_batch)} update)")
                        
                        # Create new attendances
                        if attendance_create_batch:
                            self.env['hr.attendance'].create(attendance_create_batch)
                            total_processed += len(attendance_create_batch)
                            attendance_create_batch = []
                        
                        # Update existing attendances
                        if attendance_update_batch:
                            for update_item in attendance_update_batch:
                                update_item['record'].write(update_item['vals'])
                            total_processed += len(attendance_update_batch)
                            attendance_update_batch = []
                        
                        # Commit progress to database
                        self.env.cr.commit()
                        _logger.info(f"✅ Batch #{batch_count} committed ({total_processed} total records)")

                # Move to next page
                url = data.get("next")
                params = {} 

            # Process remaining records in final batch
            if attendance_create_batch or attendance_update_batch:
                batch_count += 1
                _logger.info(f"💾 Processing final batch #{batch_count} ({len(attendance_create_batch)} create, {len(attendance_update_batch)} update)")
                
                if attendance_create_batch:
                    self.env['hr.attendance'].create(attendance_create_batch)
                    total_processed += len(attendance_create_batch)
                
                if attendance_update_batch:
                    for update_item in attendance_update_batch:
                        update_item['record'].write(update_item['vals'])
                    total_processed += len(attendance_update_batch)
                
                self.env.cr.commit()
                _logger.info(f"✅ Final batch #{batch_count} committed")

            # Update last sync time
            if not manual_start:
                ICP.set_param("biotime.last_sync_time", fields.Datetime.to_string(latest_seen.replace(tzinfo=None)))

            # Build result message
            msg_parts = [
                f"✅ Successfully synced {total_processed} attendance records",
                f"\n📊 Processed {total_api_records} API records in {batch_count} batches",
                f"\n👥 Affected {len(unique_employees)} employees"
            ]
            
            if missing_employees:
                missing_list = sorted(list(missing_employees))
                count_missing = len(missing_list)
                display_missing = ", ".join(missing_list[:5])
                if count_missing > 5:
                    display_missing += f", ... (+{count_missing - 5} more)"
                
                msg_parts.append(f"\n\n⚠️ IGNORED ({count_missing}) Unknown Employee IDs: {display_missing}")
                _logger.warning(f"Ignored BioTime Employee IDs: {missing_list}")

            final_msg = "".join(msg_parts)
            _logger.info(f"🎉 BioTime Sync Complete: {final_msg}")
            
            return {"success": True, "message": final_msg}

        except Exception as e:
            _logger.error(f"❌ Sync Error: {e}", exc_info=True)
            return {"success": False, "message": f"System Error: {str(e)}"}

# # -*- coding: utf-8 -*-
# import requests
# import logging
# from datetime import datetime, timedelta, timezone
# import pytz

# from odoo import models, fields, api, _
# from odoo.exceptions import UserError

# _logger = logging.getLogger(__name__)

# class BiotimeApiManager(models.Model):
#     _name = 'biotime.api.manager'
#     _description = 'Ahadu Bank: BioTime Integration Engine'

#     name = fields.Char(default="BioTime API Manager")

#     @api.model
#     def _get_cfg(self):
#         p = self.env["ir.config_parameter"].sudo()
#         url = p.get_param("biotime.api_url")
#         if url:
#             url = url.strip().rstrip('/')
#             if not url.startswith('http://') and not url.startswith('https://'):
#                 url = f"http://{url}"

#         cfg = {
#             "url": url,
#             "user": p.get_param("biotime.api_user"),
#             "password": p.get_param("biotime.api_password"),
#             "timeout": int(p.get_param("biotime.api_timeout", "30")),
#             "default_area_id": int(p.get_param("biotime.default_area_id", "1")),
#             "timezone": p.get_param("biotime.timezone", "Africa/Addis_Ababa"),
#         }
#         if not all([cfg["url"], cfg["user"], cfg["password"]]):
#             msg = "BioTime API parameters are missing (url, user, password)."
#             _logger.error(msg)
#             return {"error": msg}
#         return cfg

#     @api.model
#     def _get_token(self, cfg):
#         ICP = self.env["ir.config_parameter"].sudo()
#         token, token_until_str = ICP.get_param("biotime.jwt_token"), ICP.get_param("biotime.jwt_token_until")
#         now = datetime.now(timezone.utc)

#         if token and token_until_str:
#             try:
#                 # FIX: Use Odoo's safe datetime converter
#                 token_until_dt = fields.Datetime.from_string(token_until_str)
#                 if token_until_dt.replace(tzinfo=timezone.utc) > now + timedelta(minutes=5):
#                     return {"token": token}
#             except Exception: pass

#         auth_url = f"{cfg['url']}/jwt-api-token-auth/"
#         payload = {"username": cfg["user"], "password": cfg["password"]}
#         try:
#             r = requests.post(auth_url, json=payload, timeout=cfg["timeout"])
#             r.raise_for_status()
#             token = r.json().get("token")
#             if not token:
#                 msg = "BioTime auth response missing 'token'."
#                 _logger.error(msg)
#                 return {"error": msg}
            
#             until = now + timedelta(hours=6)
#             # FIX: Save datetime strings in Odoo's standard format
#             ICP.set_param("biotime.jwt_token", token)
#             ICP.set_param("biotime.jwt_token_until", fields.Datetime.to_string(until))
#             return {"token": token}
#         except requests.exceptions.RequestException as e:
#             msg = f"Failed to get BioTime API token: {e}"
#             _logger.error(msg)
#             return {"error": msg}
        
#     @api.model
#     def _api_request(self, method, url, headers, timeout, params=None, payload=None):
#         response = requests.request(method.upper(), url, headers=headers, params=params, json=payload, timeout=timeout)
#         if 400 <= response.status_code < 500:
#             _logger.error("BioTime API Client Error for URL %s: %s - %s", url, response.status_code, response.text)
#         response.raise_for_status()
#         return response

#     @api.model
#     def sync_attendance_from_biotime(self, manual_start=None, manual_end=None):
#         _logger.info("Starting BioTime -> Odoo attendance synchronization...")
#         cfg_res = self._get_cfg()
#         if "error" in cfg_res: return {"success": False, "message": cfg_res["error"]}
#         cfg = cfg_res
        
#         token_res = self._get_token(cfg)
#         if "error" in token_res: return {"success": False, "message": token_res["error"]}
#         token = token_res["token"]

#         ICP = self.env["ir.config_parameter"].sudo()
#         last_sync_str = ICP.get_param("biotime.last_sync_time")
        
#         # Get Timezone Object
#         try:
#             bt_tz = pytz.timezone(cfg["timezone"])
#         except pytz.UnknownTimeZoneError:
#             _logger.warning("Unknown timezone '%s', falling back to UTC.", cfg["timezone"])
#             bt_tz = pytz.UTC
        
#         # Determine start time (ensure it's timezone-aware UTC)
#         start_dt = None
#         end_dt = datetime.now(timezone.utc)

#         if manual_start:
#             # Manual Mode: Use provided dates
#             if isinstance(manual_start, str):
#                  start_dt = fields.Datetime.from_string(manual_start).replace(tzinfo=timezone.utc)
#             else:
#                  start_dt = manual_start.replace(tzinfo=timezone.utc)
            
#             if manual_end:
#                  if isinstance(manual_end, str):
#                      end_dt = fields.Datetime.from_string(manual_end).replace(tzinfo=timezone.utc)
#                  else:
#                      end_dt = manual_end.replace(tzinfo=timezone.utc)
            
#             _logger.info("Manual Sync Mode: Fetching from %s to %s", start_dt, end_dt)

#         elif last_sync_str:
#             # Auto/Standard Mode: Resume from last sync
#             # fields.Datetime.from_string returns naive datetime
#             naive_start = fields.Datetime.from_string(last_sync_str)
#             start_dt = naive_start.replace(tzinfo=timezone.utc)
#         else:
#             # First run fallback
#             start_dt = datetime.now(timezone.utc) - timedelta(days=1)
            
#         end_dt = datetime.now(timezone.utc)
        
#         url = f"{cfg['url']}/iclock/api/transactions/"
#         headers = {"Authorization": f"JWT {token}"}
#         # FIX: BioTime API uses 'start_time' and 'end_time', not 'start_datetime'
#         params = {
#             "start_time": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
#             "end_time": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
#             "page_size": 1000  # Attempt to fetch larger batches
#         }
        
#         _logger.info("BioTime Sync Request: %s | Params: %s", url, params)
#         _logger.info("BioTime Sync Date Window: Start=%s, End=%s", start_dt, end_dt)

#         total_processed, total_found, latest_seen = 0, 0, start_dt
        
#         try:
#             while url:
#                 # _logger.info("Fetching page: %s", url) 
#                 resp = self._api_request("GET", url, headers, cfg["timeout"], params=params)
#                 data = resp.json()
#                 page_items = data.get("data", []) or data.get("results", [])
                
#                 total_found += len(page_items)
                
#                 # DEBUG: Log the first item of the batch to see structure
#                 if page_items and total_found <= len(page_items):
#                     _logger.info("BioTime Sync Debug - First Item Raw: %s", page_items[0])

#                 for item in page_items:
#                     emp_code, punch_time_s, punch_id = item.get("emp_code"), item.get("punch_time"), item.get("id")
#                     punch_state = item.get("punch_state") # e.g. '0' (Check In), '1' (Check Out), '255' (Other), or strings
                    
#                     if not all([emp_code, punch_time_s, punch_id]): continue

#                     # BioTime sends "2026-01-01 08:00:00" which means 8 AM in Addis Ababa (if that's where the device is)
#                     # We need to tell Odoo this is 05:00:00 UTC.
#                     try:
#                         # 1. Parse naive string
#                         # Handle potential 'Z' or ISO formats, mostly it's "YYYY-MM-DD HH:MM:SS"
#                         # BioTime often sends "2023-10-27 10:00:00" space separated
#                         punch_dt_naive = datetime.fromisoformat(punch_time_s.replace(' ', 'T').replace('Z', ''))
                        
#                         # 2. Localize to BioTime Timezone (e.g., EAT)
#                         punch_dt_local = bt_tz.localize(punch_dt_naive)
                        
#                         # 3. Convert to UTC for storage/comparison
#                         punch_dt_utc = punch_dt_local.astimezone(pytz.UTC)
                        
#                         # Replace our variable for downstream logic
#                         punch_dt_aware = punch_dt_utc
                        
#                     except Exception as e:
#                         _logger.error("Error parsing/converting time '%s': %s", punch_time_s, e)
#                         continue

#                     # Ensure punch_dt_aware is actually aware (defensive programming)
#                     if punch_dt_aware.tzinfo is None:
#                         punch_dt_aware = punch_dt_aware.replace(tzinfo=timezone.utc)
                    
#                     if punch_dt_aware <= start_dt: 
#                         _logger.info("Skipped Record: Punch Time %s (UTC) <= Start Time %s (UTC)", punch_dt_aware, start_dt)
#                         continue
#                     if self.env["hr.attendance"].search_count([("biotime_punch_id", "=", punch_id)]): 
#                         _logger.info("Skipped Record: Auto-Duplicate check for punch_id %s", punch_id)
#                         continue

#                     employee = self.env["hr.employee"].search([("employee_id", "=", emp_code.strip())], limit=1)
#                     if not employee:
#                         _logger.warning("Skipped Record: Employee with Employee ID '%s' not found in Odoo.", emp_code)
#                         continue

#                     # Determine action based on punch_state if available
#                     # Common keys: 0=CheckIn, 1=CheckOut. Sometimes strings "Check In"/"Check Out"
#                     is_check_out = str(punch_state) in ['1', 'Check Out', 'CheckOut']
#                     is_check_in = str(punch_state) in ['0', 'Check In', 'CheckIn']
                    
#                     # Find last open attendance
#                     last_attendance = self.env['hr.attendance'].search([
#                         ('employee_id', '=', employee.id), ('check_out', '=', False)
#                     ], order='check_in desc', limit=1)

#                     if is_check_out:
#                          if last_attendance:
#                              last_attendance.check_out = punch_dt_aware.replace(tzinfo=None)
#                          else:
#                              # Got a Check-Out but no Check-In. 
#                              # Option A: Ignore. Option B: Create instant record? 
#                              # Let's ignore to resolve "orphaned checkouts" or maybe create a record with same in/out?
#                              # For now, let's treat it as a toggle fallback or just ignore. 
#                              # Default behavior if strict: Ignore.
#                              _logger.info("Ignored orphaned Check-Out for %s at %s", employee.name, punch_dt_aware)
#                              pass 
#                     elif is_check_in:
#                         if last_attendance:
#                             # Already checked in? Close verify previous?
#                             # Standard Odoo: Close previous with its own check_in time (0 duration) or just make new one?
#                             # Let's close the old one at current time? No, that makes huge duration.
#                             # Let's close the old one at *its* check_in + 1 min?
#                             # Or just leave it open and create a NEW open one? Odoo constraints prevent overlapping open attendances usually.
                            
#                             # Simple logic: If we force Check-In, ensures we have a new record.
#                             # If there is an open one, we must close it first to avoid overlap error? 
#                             # Odoo 18 might allow it? Usually no.
#                             # Let's auto-close the previous one to avoid errors.
#                             last_attendance.check_out = punch_dt_aware.replace(tzinfo=None)
                        
#                         self.env["hr.attendance"].create({
#                             "employee_id": employee.id,
#                             "check_in": punch_dt_aware.replace(tzinfo=None),
#                             "biotime_punch_id": punch_id,
#                             "check_in_method": "Biometric",
#                         })
#                     else:
#                         # Fallback / Toggle Logic (State 255 or undefined)
#                         if last_attendance:
#                             last_attendance.check_out = punch_dt_aware.replace(tzinfo=None)
#                         else:
#                             self.env["hr.attendance"].create({
#                                 "employee_id": employee.id,
#                                 "check_in": punch_dt_aware.replace(tzinfo=None),
#                                 "biotime_punch_id": punch_id,
#                                 "check_in_method": "Biometric",
#                             })

#                     total_processed += 1
#                     if punch_dt_aware > latest_seen: latest_seen = punch_dt_aware
                
#                 url, params = data.get("next"), {}

#             # Save as naive string for Odoo (fields.Datetime expects naive UTC)
#             if not manual_start: # Only update last_sync if regular sync
#                 ICP.set_param("biotime.last_sync_time", fields.Datetime.to_string(latest_seen.replace(tzinfo=None)))
            
#             msg = f"BioTime -> Odoo sync finished. Found {total_found} records. Processed {total_processed} new punches."
#             if manual_start:
#                 msg += f" (Range: {start_dt} to {end_dt})"
                
#             _logger.info(msg)
#             return {"success": True, "message": msg}
#         except requests.exceptions.RequestException as e:
#             msg = f"API Error during attendance sync: {e}"
#             _logger.error(msg)
#             return {"success": False, "message": msg}
#         except Exception as e:
#             msg = f"Unexpected error during attendance sync: {e}"
#             _logger.exception(msg)
#             return {"success": False, "message": msg}
    
#     #Auto sync attendance from biotime to odoo with time interval
#     @api.model
#     def cron_auto_sync_attendance(self):
#         """Automatically sync attendance data from BioTime based on cron schedule."""
#         try:
#             settings = self.env['res.config.settings'].sudo().get_values()
#             api_url = settings.get('biotime_api_url')
#             # Check basic requirements before proceeding
#             if not api_url:
#                 _logger.warning("BioTime auto-sync skipped: Missing API URL configuration.")
#                 return

#             _logger.info("🔄 Starting automatic BioTime attendance sync...")
#             # Use '1' as default area if not specified
#             # Note: We aren't passing params to sync_attendance_from_biotime here, so it uses configured defaults
#             result = self.sync_attendance_from_biotime()
#             if result.get("success"):
#                 _logger.info("✅ Automatic BioTime attendance sync completed successfully.")
#             else:
#                 _logger.error(f"❌ Automatic BioTime attendance sync failed: {result.get('message')}")
#         except Exception as e:
#             _logger.error("❌ Error during automatic BioTime attendance sync: %s", str(e))


#     # =========================================================================
#     # SECTION 3: Employee Sync (Odoo -> BioTime)
#     # =========================================================================
#     @api.model
#     def sync_employees_to_biotime(self, *args, **kwargs):
#         # SECURITY SAFEGUARD: Disabled to protect production data
#         msg = "Sync is disabled to protect production data."
#         _logger.warning(msg)
#         return {"success": True, "message": msg}