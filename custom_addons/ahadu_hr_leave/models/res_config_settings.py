from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    accrual_launch_date = fields.Datetime(
        string="Annual Leave Accrual Launch Date",
        config_parameter='ahadu_hr_leave.accrual_launch_date',
        help="Set the date and time when automatic annual leave accrual should start. "
             "Employees hired before this date will start accruing from this date (not from their joining date). "
             "This allows you to migrate historical data separately without interference."
    )

    auto_allocate_leaves = fields.Boolean(
        string="Automatically Allocate Leaves",
        help="When enabled, the system automatically creates leave allocations "
             "(Paternity, Maternity, Sick, etc.) when employees are created or updated. "
             "Disable this during data migration to prevent duplicate allocations."
    )

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        res.update(
            auto_allocate_leaves=self.env['ir.config_parameter'].sudo().get_param('ahadu_hr_leave.auto_allocate_leaves', default='True') == 'True',
        )
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        self.env['ir.config_parameter'].sudo().set_param('ahadu_hr_leave.auto_allocate_leaves', str(self.auto_allocate_leaves))
