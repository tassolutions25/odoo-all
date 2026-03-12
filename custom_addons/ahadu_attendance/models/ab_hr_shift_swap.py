# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class AbHrShiftSwapRequest(models.Model):
    _name = 'ab.hr.shift.swap.request'
    _description = 'Ahadu Bank: Employee Shift Swap Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Request Title", required=True, copy=False, readonly=True, default=lambda self: _('New'))
    requesting_employee_id = fields.Many2one('hr.employee', string="Requesting Employee", required=True, default=lambda self: self.env.user.employee_id)
    swapping_employee_id = fields.Many2one('hr.employee', string="Swap With Co-worker", required=True)
    date_of_swap = fields.Date(string="Date of Swap", required=True, default=fields.Date.today)
     # This field shows the shift the user is giving away
    my_shift_schedule_id = fields.Many2one(
        'ab.hr.shift.schedule', string="My Shift to Swap", 
        compute='_compute_my_shift', store=True, readonly=False,
        domain="[('employee_id', '=', requesting_employee_id), ('date_start', '<=', date_of_swap), ('date_end', '>=', date_of_swap)]")


    # This field shows the shift the user wants to take
    their_shift_schedule_id = fields.Many2one(
        'ab.hr.shift.schedule', string="Their Shift to Take",
        compute='_compute_their_shift', store=True, readonly=False,
        domain="[('employee_id', '=', swapping_employee_id), ('date_start', '<=', date_of_swap), ('date_end', '>=', date_of_swap)]")
    reason = fields.Text(string="Reason for Swap")
    manager_id = fields.Many2one('hr.employee', string="Approving Manager", compute='_compute_manager_id', store=True, readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string="Status", default='draft', tracking=True)

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('ab.hr.shift.swap.request') or _('New')
        return super(AbHrShiftSwapRequest, self).create(vals)

    @api.depends('requesting_employee_id', 'date_of_swap')
    def _compute_my_shift(self):
        for rec in self:
            if rec.requesting_employee_id and rec.date_of_swap:
                schedule = self.env['ab.hr.shift.schedule'].search([
                    ('employee_id', '=', rec.requesting_employee_id.id),
                    ('date_start', '<=', rec.date_of_swap),
                    ('date_end', '>=', rec.date_of_swap)
                ], limit=1)
                rec.my_shift_schedule_id = schedule.id
            else:
                rec.my_shift_schedule_id = False

    @api.depends('swapping_employee_id', 'date_of_swap')
    def _compute_their_shift(self):
        for rec in self:
            if rec.swapping_employee_id and rec.date_of_swap:
                schedule = self.env['ab.hr.shift.schedule'].search([
                    ('employee_id', '=', rec.swapping_employee_id.id),
                    ('date_start', '<=', rec.date_of_swap),
                    ('date_end', '>=', rec.date_of_swap)
                ], limit=1)
                rec.their_shift_schedule_id = schedule.id
            else:
                rec.their_shift_schedule_id = False

    @api.depends('requesting_employee_id')
    def _compute_manager_id(self):
        for record in self:
            record.manager_id = record.requesting_employee_id.parent_id if record.requesting_employee_id else False

    def action_submit(self):
        if not self.my_shift_schedule_id or not self.their_shift_schedule_id:
            raise ValidationError(_("Both employees must have a scheduled shift on the selected date to request a swap."))
        self.write({'state': 'submitted'})

    def action_approve(self):
        """This is the core logic for the swap."""
        self.ensure_one()
        
        my_schedule = self.my_shift_schedule_id
        their_schedule = self.their_shift_schedule_id

        if not my_schedule or not their_schedule:
            raise ValidationError(_("Cannot process approval. One of the original schedules is missing."))
            
        # Swap the employees on the schedule records
        my_employee = my_schedule.employee_id
        their_employee = their_schedule.employee_id
        
        my_schedule.write({'employee_id': their_employee.id})
        their_schedule.write({'employee_id': my_employee.id})
        
        # Log a note on the schedules for history
        my_schedule.message_post(body=f"Shift taken over by {my_employee.name} as part of approved swap request {self.name}.")
        their_schedule.message_post(body=f"Shift taken over by {their_employee.name} as part of approved swap request {self.name}.")

        self.write({'state': 'approved'})

    def action_reject(self):
        self.write({'state': 'rejected'})