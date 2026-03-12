from odoo import models, fields


class AhaduPayGroup(models.Model):
    _name = 'ahadu.pay.group'
    _description = 'Payroll Pay Group'
    _order = 'code'

    code = fields.Char(string='Pay Group Code', required=True)
    name = fields.Char(string='Pay Group Name', required=True)
    job_ids = fields.Many2many('hr.job', string='Job Positions', help="Job positions associated with this pay group")

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'The Pay Group Code must be unique!')
    ]
