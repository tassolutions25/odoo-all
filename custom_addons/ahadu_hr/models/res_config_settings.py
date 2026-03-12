from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    fuel_price_history_ids = fields.One2many(
        "ahadu.fuel.price.history",
        related="company_id.fuel_price_history_ids",
        string="Fuel Price History",
        readonly=False,
    )
    
    fuel_price_cutoff_date = fields.Date(
        related="company_id.fuel_price_cutoff_date",
        string="Fuel Price Cutoff Date",
        readonly=False,
    )
