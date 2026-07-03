from odoo import models, fields, api
from dateutil.relativedelta import relativedelta


class HrContract(models.Model):
    _inherit = "hr.contract"

    contract_type_id = fields.Many2one(
        "hr.contract.type",
        string="Contract Type",
        required=True,
    )

    @api.onchange("employee_id")
    def _onchange_employee_id(self):
        if self.employee_id and self.employee_id.date_of_joining:
            self.date_start = self.employee_id.date_of_joining