# -*- coding: utf-8 -*-
from odoo import models, fields, api

class AhaduBranchMapping(models.Model):
    _name = 'ahadu.branch.mapping'
    _description = 'Branch Cost Center Mapping'
    _rec_name = 'branch_id'

    branch_id = fields.Many2one('hr.branch', string='Branch', required=True, ondelete='cascade')
    cost_center_id = fields.Many2one('hr.cost.center', string='Cost Center', required=True, ondelete='restrict')

    _sql_constraints = [
        ('branch_uniq', 'unique(branch_id)', 'A mapping for this branch already exists!'),
    ]
