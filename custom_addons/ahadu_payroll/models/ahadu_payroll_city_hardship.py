from odoo import models, fields, api, _
from odoo.exceptions import UserError

class AhaduPayrollCityHardshipConfig(models.Model):
    _name = 'ahadu.payroll.city.hardship.config'
    _description = 'City Hardship Tax Exemption Config'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'city_id'

    city_id = fields.Many2one(
        'hr.city',
        string='City',
        required=True,
        ondelete='cascade',
        help="The city this hardship exemption applies to",
        tracking=True
    )

    non_taxable_percentage = fields.Float(
        string='Non-Taxable Hardship Percentage',
        default=0.0,
        help="The maximum percentage of basic salary for hardship allowance that is exempt from income tax in this city. Example: Gambella = 30.",
        tracking=True
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
    ], string="Status", default='draft', tracking=True, required=True)

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_approve(self):
        if not self.env.user.has_group('ahadu_payroll.group_ahadu_payroll_finance_manager'):
            raise UserError(_("Only HR Finance Managers can approve these rules."))
        self.write({'state': 'approved'})

    def action_draft(self):
        self.write({'state': 'draft'})

    def write(self, vals):
        for rec in self:
            if rec.state == 'approved' and not self.env.user.has_group('ahadu_payroll.group_ahadu_payroll_finance_manager'):
                raise UserError(_("You cannot modify an approved rule. Please contact an HR Finance Manager to reset it to draft."))
        return super(AhaduPayrollCityHardshipConfig, self).write(vals)

    _sql_constraints = [
        ('city_unique', 'unique(city_id)', 
         'A hardship exemption configuration already exists for this city!')
    ]

    def name_get(self):
        """Display city name in dropdowns."""
        result = []
        for record in self:
            name = record.city_id.name or 'Unnamed City'
            result.append((record.id, f"Hardship Exemption - {name}"))
        return result
