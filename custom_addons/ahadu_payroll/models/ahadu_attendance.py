# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime

class AhaduAttendanceSheet(models.Model):
    _name = 'ahadu.attendance.sheet'
    _description = 'Manual Attendance Sheet'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_from desc, employee_id'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, index=True, default=lambda self: _('New'))
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, tracking=True)
    employee_id_code = fields.Char(string='Employee ID', help="Enter Employee ID to quickly find the employee")
    branch_id = fields.Many2one('hr.branch', string='Branch', related='employee_id.branch_id', store=True)
    date_from = fields.Date(string='Date From', required=True, tracking=True)
    date_to = fields.Date(string='Date To', required=True, tracking=True)
    
    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id:
            self.employee_id_code = self.employee_id.identification_id or self.employee_id.employee_id

    @api.onchange('employee_id_code')
    def _onchange_employee_id_code(self):
        if self.employee_id_code:
            employee = self.env['hr.employee'].search([
                '|', ('identification_id', '=', self.employee_id_code),
                ('employee_id', '=', self.employee_id_code)
            ], limit=1)
            if employee:
                self.employee_id = employee.id
            else:
                # Optionally clear if not found, but better to just leave it
                pass

    state = fields.Selection([
        ('draft', 'Draft'),
        ('verified', 'Verified'),
        ('approved', 'Approved'),
        ('cancel', 'Cancelled')
    ], string='Status', default='draft', tracking=True)

    prepared_by_id = fields.Many2one('res.users', string='Prepared By', readonly=True, tracking=True)
    prepared_on = fields.Datetime(string='Prepared On', readonly=True)
    verified_by_id = fields.Many2one('res.users', string='Verified By', readonly=True, tracking=True)
    verified_on = fields.Datetime(string='Verified On', readonly=True)
    approved_by_id = fields.Many2one('res.users', string='Approved By', readonly=True, tracking=True)
    approved_on = fields.Datetime(string='Approved On', readonly=True)

    line_ids = fields.One2many('ahadu.attendance.sheet.line', 'sheet_id', string='Absent Days')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('ahadu.attendance.sheet') or _('New')
            vals['prepared_by_id'] = self.env.user.id
            vals['prepared_on'] = fields.Datetime.now()
        return super(AhaduAttendanceSheet, self).create(vals_list)

    def action_verify(self):
        for sheet in self:
            sheet.write({
                'state': 'verified',
                'verified_by_id': self.env.user.id,
                'verified_on': fields.Datetime.now()
            })

    def action_approve(self):
        # Checker Logic: Ensure the user has the manager group
        if not (self.env.user.has_group('ahadu_payroll.group_attendance_manager') or 
                self.env.user.has_group('ahadu_payroll.group_branch_attendance_manager')):
            raise UserError(_("Only Attendance Managers can approve these sheets."))
            
        for sheet in self:
            # Descriptive Name: Absent Days of John Doe from 1-1-2026 to 31-1-2026
            date_from_str = sheet.date_from.strftime('%d-%m-%Y') if sheet.date_from else ''
            date_to_str = sheet.date_to.strftime('%d-%m-%Y') if sheet.date_to else ''
            new_name = _("Absent Days of %s from %s to %s") % (sheet.employee_id.name, date_from_str, date_to_str)
            
            sheet.write({
                'name': new_name,
                'state': 'approved',
                'approved_by_id': self.env.user.id,
                'approved_on': fields.Datetime.now()
            })

    def action_draft(self):
        for sheet in self:
            if sheet.state == 'approved':
                raise UserError(_("Approved sheets cannot be reset to draft."))
            sheet.write({'state': 'draft'})

    def action_cancel(self):
        for sheet in self:
            sheet.write({'state': 'cancel'})


class AhaduAttendanceSheetLine(models.Model):
    _name = 'ahadu.attendance.sheet.line'
    _description = 'Absent Day Record'

    sheet_id = fields.Many2one('ahadu.attendance.sheet', string='Attendance Sheet', ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', related='sheet_id.employee_id', store=True)
    date = fields.Date(string='Absent Date', required=True)

    _sql_constraints = [
        ('unique_date_per_sheet', 'unique(sheet_id, date)', 'One day cannot be selected more than once for the same employee!')
    ]

    @api.constrains('date')
    def _check_date_validity(self):
        for line in self:
            sheet = line.sheet_id
            # 1. Range check
            if line.date < sheet.date_from or line.date > sheet.date_to:
                raise ValidationError(_("The date %s is outside the payroll period [%s - %s].") % (line.date, sheet.date_from, sheet.date_to))
            
            # 2. Weekend check (Assume Saturday=5, Sunday=6)
            if line.date.weekday() in [5, 6]:
                raise ValidationError(_("The date %s is a non-working day (Weekend). You cannot mark it as absent.") % line.date)

            # 3. Leave check
            leaves = self.env['hr.leave'].search([
                ('employee_id', '=', sheet.employee_id.id),
                ('state', '=', 'validate'),
                ('date_from', '<=', line.date),
                ('date_to', '>=', line.date),
            ])
            if leaves:
                raise ValidationError(_("The employee is already on approved leave on %s. You cannot mark it as absent.") % line.date)
