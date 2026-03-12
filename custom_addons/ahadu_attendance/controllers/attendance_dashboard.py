# -*- coding: utf-8 -*-
from odoo import fields
from odoo import http
from odoo.http import request

class AttendanceDashboardController(http.Controller):

    @http.route('/ahadu_attendance/dashboard/data', type='json', auth='user')
    def get_dashboard_data(self):
        env = request.env
        user = request.env.user

        # Example logic — you should adjust based on your hr.attendance, hr.leave, etc.
        total_employees = env['hr.employee'].search_count([])
        present_today = env['hr.attendance'].search_count([('check_in', '>=', fields.Date.today())])
        late_today = env['hr.attendance'].search_count([('is_late', '=', True), ('check_in', '>=', fields.Date.today())])
        absent_today = total_employees - present_today
        duties_today = env['hr.duty'].search_count([('date', '=', fields.Date.today())]) if 'hr.duty' in env else 0
        overtime_today = env['hr.overtime'].search_count([('date', '=', fields.Date.today())]) if 'hr.overtime' in env else 0
        shifts_today = env['hr.shift'].search_count([('date', '=', fields.Date.today())]) if 'hr.shift' in env else 0
        requests_today = env['hr.attendance.request'].search_count([('create_date', '>=', fields.Date.today())]) if 'hr.attendance.request' in env else 0
        holidays_today = env['hr.holidays.public.line'].search_count([('date', '=', fields.Date.today())]) if 'hr.holidays.public.line' in env else 0
        leaves_today = env['hr.leave'].search_count([('request_date_from', '<=', fields.Date.today()), ('request_date_to', '>=', fields.Date.today())])

        return {
            "employees": total_employees,
            "present": present_today,
            "late": late_today,
            "absent": absent_today,
            "duties": duties_today,
            "overtime": overtime_today,
            "shifts": shifts_today,
            "requests": requests_today,
            "holidays": holidays_today,
            "leaves": leaves_today,
        }
