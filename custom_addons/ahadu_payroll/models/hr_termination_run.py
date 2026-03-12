# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class HrTerminationRun(models.Model):
    _name = 'hr.termination.run'
    _description = 'Termination Batch'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Name', required=True)
    date_start = fields.Date(string='Date From', required=True)
    date_end = fields.Date(string='Date To', required=True, default=fields.Date.today)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('calculated', 'Calculated'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')
    ], string='Status', default='draft', tracking=True)

    branch_id = fields.Many2one(
        'hr.branch',
        string='Branch',
        help="Specific Branch for this batch. Automatically set for Branch Officers."
    )

    @api.model_create_multi
    def create(self, vals_list):
        # Auto-assign branch if user has one (Branch Officer logic)
        user = self.env.user
        emp = user.employee_id
        
        for vals in vals_list:
            if not vals.get('branch_id') and emp and hasattr(emp, 'branch_id') and emp.branch_id:
                vals['branch_id'] = emp.branch_id.id
                
        return super(HrTerminationRun, self).create(vals_list)

    slip_ids = fields.One2many('hr.termination.payslip', 'run_id', string='Payslips')

    def action_compute_sheet(self):
        for slip in self.slip_ids:
            slip.compute_sheet()
        self.state = 'calculated'

    def action_confirm(self):
        for slip in self.slip_ids:
            slip.action_confirm()
        self.state = 'done'

    def action_cancel(self):
        for slip in self.slip_ids:
            slip.action_cancel()
        self.state = 'cancel'
        
    def action_draft(self):
        self.write({'state': 'draft'})

    def action_print_excel(self):
        return {
            'type': 'ir.actions.act_url',
            'url': f'/ahadu_payroll/termination_excel/{self.id}',
            'target': 'new',
        }
