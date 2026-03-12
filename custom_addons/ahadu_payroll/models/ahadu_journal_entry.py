# -*- coding: utf-8 -*-
from odoo import models, fields, api

class AhaduJournalEntry(models.Model):
    _name = 'ahadu.journal.entry'
    _description = 'Payroll Journal Entry'
    _order = 'date desc, id desc'

    name = fields.Char(string='Reference', required=True, readonly=True)
    date = fields.Date(string='Date', required=True, default=fields.Date.context_today, readonly=True)
    payslip_run_id = fields.Many2one('hr.payslip.run', string='Payslip Batch', readonly=True)
    line_ids = fields.One2many('ahadu.journal.entry.line', 'entry_id', string='Journal Lines')
    state = fields.Selection([('draft', 'Draft'), ('posted', 'Posted')], default='posted', string='Status')

class AhaduJournalEntryLine(models.Model):
    _name = 'ahadu.journal.entry.line'
    _description = 'Journal Entry Line'

    entry_id = fields.Many2one('ahadu.journal.entry', string='Entry', ondelete='cascade')
    account_id = fields.Many2one('ahadu.account', string='GL Account', required=True)
    cost_center_id = fields.Many2one('hr.cost.center', string='Cost Center')
    description = fields.Char(string='Description')
    debit = fields.Float(string='Debit', digits=(16, 2), default=0.0)
    credit = fields.Float(string='Credit', digits=(16, 2), default=0.0)