from odoo import models, fields


class MigratedLeaveHistory(models.Model):
    _name = 'ahadu.migrated.leave.history'
    _description = 'Migrated Leave History'
    _order = 'date_from desc, id desc'

    employee_id_code = fields.Char(string='Employee ID')
    employee_name = fields.Char(string='Employee Name')
    qu_name = fields.Char(string='QU Name')
    leave_type = fields.Char(string='Leave Type')
    leave_name = fields.Char(string='Leave Name')
    date_from = fields.Date(string='From Date')
    date_to = fields.Date(string='To Date')
    total_days = fields.Float(string='Total No. of Days')
    reason = fields.Char(string='Reason')
    status = fields.Char(string='Status')
    approved_by = fields.Char(string='Approved By')
    approved_on = fields.Date(string='Approved On')
