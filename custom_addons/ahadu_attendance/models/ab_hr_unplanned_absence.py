# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class AbHrUnplannedAbsence(models.Model):
    _name = 'ab.hr.unplanned.absence'
    _description = 'Unplanned Employee Absence'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc'

    employee_id = fields.Many2one('hr.employee', string="Employee", required=True)
    manager_id = fields.Many2one(related='employee_id.parent_id', store=True)
    date = fields.Date(string="Date of Absence", required=True)
    state = fields.Selection([
        ('detected', 'Detected'),
        ('confirmed', 'Confirmed'),
        ('excused', 'Excused'),
    ], string="Status", default='detected', tracking=True)
    notes = fields.Text(string="Manager Notes")

    def action_confirm(self):
        self.write({'state': 'confirmed'})
        # You could trigger a disciplinary note from here if needed
        
    def action_excuse(self):
        self.write({'state': 'excused'})