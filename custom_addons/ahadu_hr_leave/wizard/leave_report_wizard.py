from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime
from dateutil.relativedelta import relativedelta

class LeaveReportWizard(models.TransientModel):
    _name = 'ahadu.leave.report.wizard'
    _description = 'Comprehensive Leave Report Wizard'

    report_type = fields.Selection([
        ('balance', 'Employee Leave Balance'),
        ('request', 'Leave Request Summary'),
        ('audit', 'Compliance / HR Audit'),
        ('trend', 'Leave Trend / Analytics'),
        ('approval', 'Manager Approval Efficiency')
    ], string='Report Type', default='balance', required=True)

    date_from = fields.Date(string='Start Date', default=lambda self: fields.Date.today().replace(day=1))
    date_to = fields.Date(string='End Date', default=fields.Date.today)

    employee_ids = fields.Many2many('hr.employee', string='Employees')
    department_ids = fields.Many2many('hr.department', string='Departments')
    leave_type_ids = fields.Many2many('hr.leave.type', string='Leave Types')
    
    status = fields.Selection([
        ('draft', 'To Submit'),
        ('confirm', 'To Approve'),
        ('validate1', 'Second Approval'),
        ('validate', 'Approved'),
        ('refuse', 'Refused'),
        ('cancel', 'Cancelled')
    ], string='Status')

    # Access control helper
    is_hr_officer = fields.Boolean(compute='_compute_is_hr_officer')

    @api.depends_context('uid')
    def _compute_is_hr_officer(self):
        for wizard in self:
            wizard.is_hr_officer = self.env.user.has_group('ahadu_hr_leave.group_leave_officer') or \
                                   self.env.user.has_group('hr_holidays.group_hr_holidays_manager')

    def _get_allowed_employees(self):
        """Helper to return employees allowed based on user role and wizard filters."""
        allowed_employees = self.env['hr.employee']
        if self.is_hr_officer:
            allowed_employees = self.env['hr.employee'].search([]) 
        elif self.env.user.has_group('hr_holidays.group_hr_holidays_user'):
            allowed_employees = self.env.user.employee_id | self.env['hr.employee'].search([
                ('parent_id', 'child_of', self.env.user.employee_id.id)
            ])
        else:
            allowed_employees = self.env.user.employee_id

        final_employees = self.employee_ids & allowed_employees if self.employee_ids else allowed_employees
        if self.department_ids:
            final_employees = final_employees.filtered(lambda e: e.department_id in self.department_ids)
        return final_employees

    def get_balance_data(self):
        employees = self._get_allowed_employees()
        report_data = []
        for emp in employees:
            domain = [('employee_id', '=', emp.id), ('state', '=', 'validate')]
            if self.leave_type_ids:
                domain.append(('holiday_status_id', 'in', self.leave_type_ids.ids))
            allocations = self.env['hr.leave.allocation'].search(domain)
            for l_type in allocations.mapped('holiday_status_id'):
                type_allocs = allocations.filtered(lambda a: a.holiday_status_id == l_type)
                report_data.append({
                    'employee': emp.name,
                    'leave_type': l_type.name,
                    'allocated': sum(type_allocs.mapped('number_of_days')),
                    'used': sum(type_allocs.mapped('leaves_taken')),
                    'remaining': sum(type_allocs.mapped('effective_remaining_leaves')),
                })
        return report_data

    def get_request_data(self):
        employees = self._get_allowed_employees()
        domain = [('employee_id', 'in', employees.ids)]
        if self.date_from: domain.append(('request_date_from', '>=', self.date_from))
        if self.date_to: domain.append(('request_date_to', '<=', self.date_to))
        if self.status: domain.append(('state', '=', self.status))
        if self.leave_type_ids: domain.append(('holiday_status_id', 'in', self.leave_type_ids.ids))
        return self.env['hr.leave'].search(domain, order='request_date_from desc')

    def get_audit_data(self):
        employees = self._get_allowed_employees()
        audit_lines = []
        today = fields.Date.today()
        soon = today + relativedelta(days=30)
        for emp in employees:
            bal = sum(self.env['hr.leave.allocation'].search([
                ('employee_id', '=', emp.id), ('state', '=', 'validate')
            ]).mapped('effective_remaining_leaves'))
            if bal > 30:
                audit_lines.append({'employee': emp.name, 'issue': 'Excess Leave', 'details': f'{bal:.1f} days remaining'})
        expiring = self.env['hr.leave.allocation'].search([
            ('employee_id', 'in', employees.ids), ('state', '=', 'validate'),
            ('expiry_date', '>=', today), ('expiry_date', '<=', soon),
            ('effective_remaining_leaves', '>', 0)
        ])
        for alloc in expiring:
            audit_lines.append({'employee': alloc.employee_id.name, 'issue': 'Carry Forward Expiry', 'details': f'{alloc.effective_remaining_leaves:.1f} days expire on {alloc.expiry_date}'})
        return audit_lines

    def get_trend_data(self):
        employees = self._get_allowed_employees()
        domain = [('employee_id', 'in', employees.ids), ('state', '=', 'validate')]
        if self.date_from: domain.append(('request_date_from', '>=', self.date_from))
        if self.date_to: domain.append(('request_date_to', '<=', self.date_to))
        leaves = self.env['hr.leave'].search(domain)
        trend_data = {}
        for leave in leaves:
            month = leave.request_date_from.strftime('%Y-%m')
            trend_data[month] = trend_data.get(month, 0) + leave.number_of_days
        return [{'month': m, 'days': d} for m, d in sorted(trend_data.items())]

    def get_approval_data(self):
        managers = self.env['hr.employee'].search([('child_ids', '!=', False)])
        approval_data = []
        for manager in managers:
            pending = self.env['hr.leave'].search_count([
                ('employee_id.parent_id', '=', manager.id),
                ('state', 'in', ['confirm', 'validate1'])
            ])
            approved = self.env['hr.leave'].search_count([
                ('employee_id.parent_id', '=', manager.id),
                ('state', '=', 'validate')
            ])
            if pending > 0 or approved > 0:
                approval_data.append({'manager': manager.name, 'pending': pending, 'approved': approved})
        return approval_data

    def action_print_report(self):
        self.ensure_one()
        report_ref = {
            'balance': 'ahadu_hr_leave.action_report_leave_balance_comprehensive',
            'request': 'ahadu_hr_leave.action_report_leave_request_summary',
            'audit': 'ahadu_hr_leave.action_report_leave_audit',
            'trend': 'ahadu_hr_leave.action_report_leave_trend',
            'approval': 'ahadu_hr_leave.action_report_leave_approval_efficiency'
        }.get(self.report_type)
        return self.env.ref(report_ref).report_action(self)
