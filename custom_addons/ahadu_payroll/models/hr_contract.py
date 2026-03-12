from odoo import models, fields, api

class HrContract(models.Model):
    _inherit = 'hr.contract'

    @api.model
    def default_get(self, fields_list):
        defaults = super(HrContract, self).default_get(fields_list)
        if 'struct_id' in fields_list and not defaults.get('struct_id'):
            structure = self.env.ref('ahadu_payroll.structure_ahadu_monthly', raise_if_not_found=False)
            if structure:
                defaults['struct_id'] = structure.id
        return defaults

    cost_center_id = fields.Many2one(
        'hr.cost.center', 
        related='employee_id.cost_center_id', 
        string='Cost Center', 
        store=True, 
        readonly=False,
        tracking=True
    )
    pay_group_id = fields.Many2one('ahadu.pay.group', string='Pay Group', tracking=True)
    
    # Re-adding per-employee fuel liters (Related from Employee)
    fuel_liters = fields.Float(
        string='Fuel (Liters)', 
        related='employee_id.transport_allowance_liters',
        readonly=False,
        help="Monthly fuel allowance in liters (Synced with Employee)"
    )