# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class HrAttendancePolicyAllocation(models.Model):
    _name = 'hr.attendance.policy.allocation'
    _description = 'Attendance Policy Allocation'

    name = fields.Char(compute='_compute_name', store=True)
    policy_id = fields.Many2one('hr.attendance.policy', string="Attendance Policy", required=True)
    
    allocation_type = fields.Selection([
        ('all', 'All Employees'),
        ('department', 'By Department'),
        ('employee', 'Specific Employees'),
    ], string="Allocate To", default='department', required=True)
    
    department_ids = fields.Many2many('hr.department', string="Departments")
    employee_ids = fields.Many2many('hr.employee', string="Employees")

    @api.depends('policy_id', 'allocation_type', 'department_ids', 'employee_ids')
    def _compute_name(self):
        for alloc in self:
            target = "All Employees"
            if alloc.allocation_type == 'department' and alloc.department_ids:
                target = ', '.join(alloc.department_ids.mapped('name'))
            elif alloc.allocation_type == 'employee':
                target = f"{len(alloc.employee_ids)} employees"
            alloc.name = f"'{alloc.policy_id.name}' for {target}"

    def action_apply_allocation(self):
        target_employees = self.env['hr.employee']
        if self.allocation_type == 'all':
            target_employees = self.env['hr.employee'].search([('active', '=', True)])
        elif self.allocation_type == 'department':
            target_employees = self.env['hr.employee'].search([('department_id', 'in', self.department_ids.ids)])
        elif self.allocation_type == 'employee':
            target_employees = self.employee_ids
            
        target_employees.write({
            'attendance_policy_id': self.policy_id.id,
            'resource_calendar_id': self.policy_id.resource_calendar_id.id,
        })
        return {'type': 'ir.actions.act_window_close'}