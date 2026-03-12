# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import logging
import pytz
from datetime import datetime

_logger = logging.getLogger(__name__)

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    @api.model
    def _tz_get(self):
        return [(tz, tz) for tz in pytz.common_timezones]

    # --- BioTime API Settings ---
    biotime_api_url = fields.Char(string="BioTime API URL", config_parameter='biotime.api_url')
    biotime_api_user = fields.Char(string="BioTime API Username", config_parameter='biotime.api_user')
    biotime_api_password = fields.Char(string="BioTime API Password", config_parameter='biotime.api_password', password=True)
    biotime_api_timeout = fields.Integer(string="API Timeout (seconds)", config_parameter='biotime.api_timeout', default=30)
    biotime_default_area_id = fields.Integer(string="BioTime Default Area ID", config_parameter='biotime.default_area_id', default=1)
    
    biotime_timezone = fields.Selection(
        _tz_get, string='BioTime Timezone',
        default='Africa/Addis_Ababa',
        config_parameter='biotime.timezone',
        help="The timezone of the BioTime server/devices."
    )
    
    biotime_auto_sync_interval = fields.Integer(
        string="Auto Sync Interval (minutes)",
        config_parameter='ahadu_attendance.biotime_auto_sync_interval',
        default=30
    )

    biotime_last_sync_time = fields.Datetime(
        string="Last Attendance Sync",
        readonly=True,
        config_parameter='biotime.last_sync_time'
    )

    # --- Manual Sync Date Range ---
    biotime_manual_start_date = fields.Datetime(
        string="Manual Sync Start Date",
        config_parameter='biotime.manual_start_date' 
    )
    biotime_manual_end_date = fields.Datetime(
        string="Manual Sync End Date",
        config_parameter='biotime.manual_end_date'
    )

    # --- Database Connection Settings ---
    biotime_db_host = fields.Char(string="DB Host", config_parameter='biotime.db_host', default='10.1.9.12')
    biotime_db_port = fields.Char(string="DB Port", config_parameter='biotime.db_port', default='53779')
    biotime_db_name = fields.Char(string="DB Name", config_parameter='biotime.db_name', default='zkbiotime')
    biotime_db_user = fields.Char(string="DB User", config_parameter='biotime.db_user', default='erpuserbi')
    biotime_db_password = fields.Char(string="DB Password", config_parameter='biotime.db_password', password=True)

    #  --- ACTION 1: Sync Attendance (API) ---
    def action_sync_attendance_from_biotime(self):
        """Button to manually trigger the API sync."""
        ICP = self.env['ir.config_parameter'].sudo()
        start_str = ICP.get_param('biotime.manual_start_date')
        end_str = ICP.get_param('biotime.manual_end_date')

        if not start_str:
            return self._return_notification('warning', "Missing Configuration", "Please enter a Start Date and click SAVE before syncing.")

        _logger.info("Starting manual Attendance Sync from BioTime API...")
        try:
            result = self.env['biotime.api.manager'].sync_attendance_from_biotime(
                manual_start=start_str,
                manual_end=end_str
            )
            return self._handle_sync_result(result)
        except Exception as e:
            _logger.exception("Exception during API Sync")
            return self._return_notification('danger', "System Error", str(e))

    # --- ACTION 2: Sync Attendance (Database - Recommended) ---
    def action_sync_attendance_from_db(self):
        """Button to trigger Direct DB Sync"""
        ICP = self.env['ir.config_parameter'].sudo()
        start_str = ICP.get_param('biotime.manual_start_date')
        end_str = ICP.get_param('biotime.manual_end_date')

        if not start_str or not end_str:
            return self._return_notification('warning', "Dates Missing", "Please enter Start and End dates and click SAVE.")

        _logger.info("Starting Direct Database Sync (MSSQL)...")
        try:
            # Call the DB Manager
            result = self.env['biotime.db.manager'].sync_attendance_db_daily_summary(
                start_str, end_str
            )
            return self._handle_sync_result(result)
        except Exception as e:
            _logger.error(f"Sync failed in settings: {e}")
            return self._return_notification('danger', "Connection Error", str(e))

    # --- ACTION 3: Sync Employees ---
    def action_sync_employees_to_biotime(self):
        _logger.info("Starting manual Employee Sync to BioTime...")
        try:
            result = self.env['biotime.api.manager'].sync_employees_to_biotime()
            return self._handle_sync_result(result)
        except Exception as e:
            _logger.exception("Exception during Employee Sync")
            return self._return_notification('danger', "Error", str(e))

    # --- Helper Methods ---
    def _handle_sync_result(self, result):
        if not result:
            return self._return_notification('warning', "No Result", "The sync process finished but returned no data.")
            
        if not result.get('success'):
            return self._return_notification('danger', "Sync Failed", result.get('message', 'Unknown Error'))
            
        msg = result.get('message')
        has_warnings = "IGNORED" in msg or "⚠️" in msg
        return self._return_notification(
            'warning' if has_warnings else 'success',
            "Sync Completed" if has_warnings else "Success",
            msg,
            sticky=True # Always sticky so user sees the report
        )

    def _return_notification(self, type, title, message, sticky=False):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': type,
                'title': _(title),
                'message': message,
                'sticky': sticky,
            }
        }

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        res.update({
            'biotime_auto_sync_interval': int(self.env['ir.config_parameter'].sudo().get_param('ahadu_attendance.biotime_auto_sync_interval', default=30)),
        })
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        self.env['ir.config_parameter'].sudo().set_param('ahadu_attendance.biotime_auto_sync_interval', self.biotime_auto_sync_interval)

