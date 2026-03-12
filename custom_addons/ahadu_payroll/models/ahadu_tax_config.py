# -*- coding: utf-8 -*-
from odoo import fields, models, api

class AhaduPayrollTaxBracket(models.Model):
    _name = 'ahadu.payroll.tax.bracket'
    _description = 'Payroll Tax Bracket'
    _order = 'lower_bound asc'

    lower_bound = fields.Float(string='Lower Bound (ETB)', required=True)
    upper_bound = fields.Float(string='Upper Bound (ETB)', help="Enter 0 for infinity (Above X)")
    rate = fields.Float(string='Tax Rate (%)', required=True)
    deduction = fields.Float(string='Deduction (ETB)', required=True)
    active = fields.Boolean(default=True)
    
    display_range = fields.Char(string='Income Range', compute='_compute_display_range')

    @api.depends('lower_bound', 'upper_bound')
    def _compute_display_range(self):
        for record in self:
            if record.upper_bound == 0:
                record.display_range = f"Above {record.lower_bound:,.2f}"
            else:
                record.display_range = f"{record.lower_bound:,.2f} - {record.upper_bound:,.2f}"


class AhaduPayrollTaxConfig(models.Model):
    _name = 'ahadu.payroll.tax.config'
    _description = 'Taxation Rules & Fuel Rate Dashboard'

    def _get_default_fuel_price(self):
        return float(self.env['ir.config_parameter'].sudo().get_param('ahadu_hr.fuel_price_per_liter', default=0.0))

    name = fields.Char(default="Payroll Parameters", readonly=True)
    
    # Fuel Information (Mapped from ahadu_hr)
    fuel_price_per_liter = fields.Float(
        string='Current Fuel Price', 
        compute='_compute_fuel_info',
        help="Current price per liter of fuel (managed in Settings)"
    )
    fuel_price_cutoff_date = fields.Date(
        string='Fuel Price Cutoff Date',
        compute='_compute_fuel_info',
        help="Cutoff date for fuel price adjustments"
    )
    fuel_price_history_ids = fields.One2many(
        'ahadu.fuel.price.history',
        compute='_compute_fuel_info',
        string='Fuel Price History'
    )

    tax_bracket_ids = fields.One2many(
        'ahadu.payroll.tax.bracket',
        compute='_compute_tax_brackets',
        string='Income Tax Brackets'
    )

    # Region Configuration
    region_config_ids = fields.One2many(
        'ahadu.payroll.region.config',
        compute='_compute_region_configs',
        string='Region Fuel Tax Deduction Config'
    )

    def _compute_fuel_info(self):
        company = self.env.company
        for record in self:
            record.fuel_price_per_liter = float(self.env['ir.config_parameter'].sudo().get_param('ahadu_hr.fuel_price_per_liter', default=0.0))
            record.fuel_price_cutoff_date = company.fuel_price_cutoff_date
            record.fuel_price_history_ids = company.fuel_price_history_ids

    def _compute_tax_brackets(self):
        brackets = self.env['ahadu.payroll.tax.bracket'].search([('active', '=', True)])
        for record in self:
            record.tax_bracket_ids = brackets

    def _compute_region_configs(self):
        configs = self.env['ahadu.payroll.region.config'].search([])
        for record in self:
            record.region_config_ids = configs
