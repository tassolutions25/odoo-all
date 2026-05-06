# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AbHrUnplannedAbsence(models.Model):
    _name = 'ab.hr.unplanned.absence'
    _description = 'Unauthorized Employee Absence'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_from desc'

    employee_id = fields.Many2one('hr.employee', string="Employee", required=True, tracking=True,
                                   default=lambda self: self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1))
    manager_id = fields.Many2one(related='employee_id.parent_id', store=True, tracking=True)
    date_from = fields.Date(string="Date From", required=True, tracking=True, default=fields.Date.context_today)
    date_to = fields.Date(string="Date To", required=True, tracking=True, default=fields.Date.context_today)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('detected', 'Detected'),
        ('waiting_justification', 'Waiting Justification'),
        ('confirmed', 'Confirmed (Unexcused)'),
        ('excused', 'Excused'),
    ], string="Status", default='draft', tracking=True)
    justification = fields.Text(string="Employee Justification", tracking=True)
    notes = fields.Text(string="Manager Notes", tracking=True)

    # ===================================================================
    #  EMPLOYEE ACTIONS
    # ===================================================================

    def action_submit(self):
        """Employee fills in their own UPA and submits it to the manager."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Only draft records can be submitted."))
            if not rec.justification:
                raise UserError(_("Please provide a justification/reason before submitting."))
            rec.write({'state': 'submitted'})
            # Notify manager
            if rec.manager_id.user_id:
                rec.activity_schedule(
                    'mail.mail_activity_data_todo',
                    summary=_("Review Unauthorized Absence submitted by %s from %s to %s") % (rec.employee_id.name, rec.date_from.strftime('%Y-%m-%d'), rec.date_to.strftime('%Y-%m-%d')),
                    user_id=rec.manager_id.user_id.id
                )

    # ===================================================================
    #  SYSTEM / CRON ACTIONS (auto-detected absences)
    # ===================================================================

    def action_request_justification(self):
        """Called automatically by cron when an absence is auto-detected."""
        for rec in self:
            if rec.state in ('draft', 'detected'):
                rec.write({'state': 'waiting_justification'})
                if rec.employee_id.user_id:
                    rec.activity_schedule(
                        'mail.mail_activity_data_todo',
                        summary=_("Please provide justification for your unauthorized absence from %s to %s") % (rec.date_from.strftime('%Y-%m-%d'), rec.date_to.strftime('%Y-%m-%d')),
                        user_id=rec.employee_id.user_id.id
                    )

    def action_submit_justification(self):
        """Employee submits their justification for a system-detected absence."""
        for rec in self:
            if not rec.justification:
                raise UserError(_("You must provide a justification before submitting."))
            rec.write({'state': 'submitted'})
            # Clear employee's activity
            rec.activity_feedback(['mail.mail_activity_data_todo'])
            # Notify manager
            if rec.manager_id.user_id:
                rec.activity_schedule(
                    'mail.mail_activity_data_todo',
                    summary=_("Justification submitted for Unauthorized Absence: %s from %s to %s") % (rec.employee_id.name, rec.date_from.strftime('%Y-%m-%d'), rec.date_to.strftime('%Y-%m-%d')),
                    user_id=rec.manager_id.user_id.id
                )

    # ===================================================================
    #  MANAGER ACTIONS
    # ===================================================================

    def action_confirm(self):
        """Manager confirms the absence is unexcused."""
        for rec in self:
            rec.write({'state': 'confirmed'})
            rec.activity_unlink(['mail.mail_activity_data_todo'])

    def action_excuse(self):
        """Manager excuses the absence."""
        for rec in self:
            rec.write({'state': 'excused'})
            rec.activity_unlink(['mail.mail_activity_data_todo'])