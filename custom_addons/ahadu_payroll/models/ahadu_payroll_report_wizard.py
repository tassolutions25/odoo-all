# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from datetime import date
from dateutil.relativedelta import relativedelta

class AhaduPayrollCustomReportWizard(models.TransientModel):
    _name = 'ahadu.payroll.custom.report'
    _description = 'Custom Payroll Report Wizard'

    date_from = fields.Date(
        string='Date From', 
        required=True, 
        default=lambda self: date.today().replace(day=1)
    )
    date_to = fields.Date(
        string='Date To', 
        required=True, 
        default=lambda self: (date.today().replace(day=1) + relativedelta(months=1)) - relativedelta(days=1)
    )
    
    pay_group_ids = fields.Many2many(
        'ahadu.pay.group', 
        string='Pay Groups',
        help="Filter by specific pay groups. Leave empty for all."
    )
    branch_ids = fields.Many2many(
        'hr.branch', 
        string='Branches',
        help="Filter by specific branches. Leave empty for all."
    )
    department_ids = fields.Many2many(
        'hr.department', 
        string='Departments',
        help="Filter by specific departments. Leave empty for all."
    )

    def action_generate_excel(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/ahadu_payroll/custom_payroll_report/{self.id}',
            'target': 'new',
        }
