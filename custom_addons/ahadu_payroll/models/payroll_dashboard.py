from odoo import models, fields, api

class AhaduPayrollDashboard(models.TransientModel):
    _name = 'ahadu.payroll.dashboard'
    _description = 'Payroll Dashboard'

    name = fields.Char(default="Payroll Dashboard")

    def action_go_to_payslip_batches(self):
        return self.env.ref('ahadu_payroll.action_ahadu_payslip_run').read()[0]

    def action_go_to_cash_indemnity(self):
        return self.env.ref('ahadu_payroll.action_cash_indemnity_tracking').read()[0]

    def action_go_to_overtime(self):
        return self.env.ref('ahadu_payroll.action_ahadu_overtime_tracking').read()[0]

    def action_go_to_taxation_rules(self):
        return self.env.ref('ahadu_payroll.action_ahadu_payroll_tax_config').read()[0]

    def action_go_to_fuel_rate(self):
        # Same as taxation rules as they are consolidated
        return self.env.ref('ahadu_payroll.action_ahadu_payroll_tax_config').read()[0]

    def action_go_to_loan(self):
        return self.env.ref('ahadu_payroll.action_hr_loan').read()[0]
