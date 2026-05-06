from odoo import models, fields, api, _
from odoo.exceptions import UserError

class AhaduPayrollRegionConfig(models.Model):
    _name = 'ahadu.payroll.region.config'
    _description = 'Region Fuel Tax Deduction Config'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'region_id'

    region_id = fields.Many2one(
        'hr.region',
        string='Region',
        required=True,
        ondelete='cascade',
        help="The region this configuration applies to",
        tracking=True
    )
    
    transport_allowance_exemption = fields.Float(
        string='Transport Allowance Exemption',
        default=600.0,
        help="Tax-exempt amount for transport allowance in this region (ETB). "
             "Example: Addis Ababa = 600, Oromia = 1000",
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
        return super(AhaduPayrollRegionConfig, self).write(vals)
    
    # Extensible: Add more region-specific fields here as needed
    # Example future fields:
    # housing_exemption = fields.Float(...)
    # hardship_multiplier = fields.Float(...)
    
    _sql_constraints = [
        ('region_unique', 'unique(region_id)', 
         'A payroll configuration already exists for this region!')
    ]
    
    def name_get(self):
        """Display region name in dropdowns."""
        result = []
        for record in self:
            name = record.region_id.name or 'Unnamed Region'
            result.append((record.id, f"Fuel Tax Deduction - {name}"))
        return result
