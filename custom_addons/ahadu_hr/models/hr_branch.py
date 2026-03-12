from odoo import models, fields, api, _


class HrBranch(models.Model):
    _name = "hr.branch"
    _description = "Branch"
    _order = "name"
    _check_company_auto = True

    name = fields.Char(string="Branch Name", required=True)
    code = fields.Char(string="Branch Code", size=10)
    district_id = fields.Many2one("hr.district", string="District", ondelete="set null")
    region_id = fields.Many2one("hr.region", string="Region", ondelete="set null")
    city_id = fields.Many2one("hr.city", string="City", ondelete="set null", domain="[('region_id', '=', region_id)]" if region_id else "[]")
    cost_center_id = fields.Many2one("hr.cost.center", string="Cost Center", ondelete="set null")
    address = fields.Text(string="Address")
    active = fields.Boolean(string="Active", default=True)

    @api.onchange("city_id")
    def _onchange_city(self):
        if self.city_id and self.city_id.region_id:
            self.region_id = self.city_id.region_id.id

    _sql_constraints = [
        (
            "code_uniq",
            "unique(code, company_id)",
            "The Branch Code must be unique per company.",
        ),
        (
            "name_district_uniq",
            "unique(name, district_id, company_id)",
            "A branch with this name already exists in this district.",
        ),
    ]
