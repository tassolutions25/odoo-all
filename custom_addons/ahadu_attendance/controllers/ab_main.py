# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request, Response
import json

class AhaduAttendanceAPI(http.Controller):

    @http.route('/api/ahadu/checkin', type='json', auth='user', methods=['POST'], csrf=False)
    def api_check_in(self, **kwargs):
        """
        API Endpoint for external devices to record attendance.
        Requires authentication (user login or API key).
        
        Expected JSON payload:
        {
            "employee_pin": "12345", // PIN or Badge ID
            "check_in_method": "Biometric",
            "device_mac_address": "AA:BB:CC:DD:EE:FF",
            "gps_location": "9.005401, 38.763611" // Optional
        }
        """
        data = request.jsonrequest
        
        if not data.get('employee_pin'):
            return {'status': 'error', 'message': 'Employee PIN is required.'}
            
        # Find employee by PIN (assuming you add a 'pin' field to hr.employee)
        # For this example, we'll use barcode, which is a standard field
        employee = request.env['hr.employee'].sudo().search([('barcode', '=', data.get('employee_pin'))], limit=1)
        if not employee:
            return {'status': 'error', 'message': 'Employee not found.'}
        
        # Check if already checked in
        if employee.attendance_state == 'checked_in':
            # This is a check-out
            attendance = request.env['hr.attendance'].sudo().search([
                ('employee_id', '=', employee.id),
                ('check_out', '=', False)
            ], limit=1)
            if attendance:
                attendance.write({'check_out': http.request.env.cr.now()})
                return {'status': 'success', 'message': f'Checked out: {employee.name}'}
            else:
                return {'status': 'error', 'message': 'Cannot check out, no active check-in found.'}
        
        else:
            # This is a check-in
            try:
                vals = {
                    'employee_id': employee.id,
                    'check_in_method': data.get('check_in_method', 'Biometric'),
                    'device_mac_address': data.get('device_mac_address'),
                    'check_in_gps': data.get('gps_location'),
                }
                attendance = request.env['hr.attendance'].sudo().create(vals)
                return {'status': 'success', 'message': f'Checked in: {employee.name}', 'attendance_id': attendance.id}
            except Exception as e:
                return {'status': 'error', 'message': str(e)}