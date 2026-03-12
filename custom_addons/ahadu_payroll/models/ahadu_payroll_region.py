# -*- coding: utf-8 -*-
from odoo import models, fields, api


class AhaduPayrollRegionConfig(models.Model):
    _name = 'ahadu.payroll.region.config'
    _description = 'Region Fuel Tax Deduction Config'
    _order = 'region_id'

    region_id = fields.Many2one(
        'hr.region',
        string='Region',
        required=True,
        ondelete='cascade',
        help="The region this configuration applies to"
    )
    
    transport_allowance_exemption = fields.Float(
        string='Transport Allowance Exemption',
        default=600.0,
        help="Tax-exempt amount for transport allowance in this region (ETB). "
             "Example: Addis Ababa = 600, Oromia = 1000"
    )
    
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
