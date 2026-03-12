from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)

class AhaduFuelPriceHistory(models.Model):
    _name = "ahadu.fuel.price.history"
    _description = "Fuel Price History"
    _order = "effective_date desc, create_date desc"
    _rec_name = "price"

    price = fields.Float(string="Price per Liter", required=True)
    effective_date = fields.Date(
        string="Effective Date", 
        required=True, 
        default=fields.Date.context_today
    )
    user_id = fields.Many2one(
        "res.users", 
        string="Changed By", 
        default=lambda self: self.env.user, 
        readonly=True
    )
    company_id = fields.Many2one(
        "res.company", 
        string="Company", 
        required=True, 
        default=lambda self: self.env.company,
        ondelete="cascade",
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self._trigger_allowance_recomputation()
        return records

    def write(self, vals):
        res = super().write(vals)
        self._trigger_allowance_recomputation()
        return res

    def _trigger_allowance_recomputation(self):
        """
        Trigger re-computation of transport allowance for all relevant employees
        when the fuel price history is modified.
        """
        self.env["hr.employee"]._recompute_all_transport_allowances()


class ResCompany(models.Model):
    _inherit = "res.company"

    fuel_price_history_ids = fields.One2many(
        "ahadu.fuel.price.history", 
        "company_id", 
        string="Fuel Price History"
    )

    fuel_price_cutoff_date = fields.Date(
        string="Fuel Price Cutoff Date",
        help="Date used to determine the cutoff for fuel price calculations. Adjustments for price changes after this date in the previous month will be added to the current month's allowance.",
        default=fields.Date.today,
    )
