# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class HrTerminationRun(models.Model):
    _name = 'hr.termination.run'
    _description = 'Termination Batch'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Name', required=True)
    date_start = fields.Date(string='Date From', required=True)
    date_end = fields.Date(string='Date To', required=True, default=fields.Date.today)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('calculated', 'Calculated'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')
    ], string='Status', default='draft', tracking=True)

    branch_id = fields.Many2one(
        'hr.branch',
        string='Branch',
        help="Specific Branch for this batch. Automatically set for Branch Officers."
    )
    
    prepared_by_id = fields.Many2one(
        'res.users', 
        string='Prepared By', 
        readonly=True, 
        tracking=True
    )
    approved_by_id = fields.Many2one(
        'res.users', 
        string='Approved By', 
        readonly=True, 
        tracking=True
    )
    bank_transfer_done = fields.Boolean(
        string='Bank Transfer Done',
        default=False,
        copy=False,
        readonly=True,
        tracking=True,
        help="Technical field to track if bank transfer was executed."
    )

    @api.model_create_multi
    def create(self, vals_list):
        self._check_manager_restriction()
        # Auto-assign branch if user has one (Branch Officer logic)
        user = self.env.user
        emp = user.employee_id
        
        for vals in vals_list:
            if not vals.get('branch_id') and emp and hasattr(emp, 'branch_id') and emp.branch_id:
                vals['branch_id'] = emp.branch_id.id
                
        return super(HrTerminationRun, self).create(vals_list)

    def write(self, vals):
        if any(run.state == 'draft' for run in self):
            if not all(k in ['state', 'message_follower_ids', 'activity_ids', 'message_ids'] for k in vals.keys()):
                self._check_manager_restriction()
        return super(HrTerminationRun, self).write(vals)

    def unlink(self):
        self._check_manager_restriction()
        return super(HrTerminationRun, self).unlink()

    def _check_manager_restriction(self):
        """Helper to block Managers from Maker actions."""
        if self.env.user.has_group('payroll.group_payroll_manager'):
            if not self.env.user.has_group('base.group_system'):
                from odoo.exceptions import AccessError
                raise AccessError(_("Payroll Managers are restricted from this action (Create/Edit). This action is reserved for Payroll Officers."))

    slip_ids = fields.One2many('hr.termination.payslip', 'run_id', string='Payslips')

    def action_compute_sheet(self):
        for run in self:
            run.prepared_by_id = self.env.user.id
        for slip in self.slip_ids:
            slip.compute_sheet()
        self.state = 'calculated'

    def action_confirm(self):
        if not self.env.user.has_group('payroll.group_payroll_manager'):
             raise UserError(_("Only Payroll Managers can approve termination batches."))
        for run in self:
            run.approved_by_id = self.env.user.id
        for slip in self.slip_ids:
            slip.action_confirm()
        self.state = 'done'

    def action_cancel(self):
        for slip in self.slip_ids:
            slip.action_cancel()
        self.state = 'cancel'
        
    def action_draft(self):
        if any(run.state == 'done' for run in self):
            raise UserError(_("This termination batch is already Done/Approved. You cannot reset it to Draft."))
        self.write({
            'state': 'draft',
            'bank_transfer_done': False
        })

    def action_print_excel(self):
        return {
            'type': 'ir.actions.act_url',
            'url': f'/ahadu_payroll/termination_excel/{self.id}',
            'target': 'new',
        }

    def action_print_bank_transfer(self):
        """Returns a URL action to download the Excel file and generate Bank Transfer."""
        self.ensure_one()
        if self.state not in ['calculated', 'done']:
            raise UserError(_("You cannot generate the Bank Transfer File until the payroll batch is Verified or Closed."))
        if self.bank_transfer_done:
            raise UserError(_("The Bank Transfer has already been processed for this batch. You cannot pay twice."))
            
        return {
            'type': 'ir.actions.act_url',
            'url': f'/ahadu_payroll/termination_bank_transfer/{self.id}',
            'target': 'new',
        }

    def action_generate_payslips(self):
        self._check_manager_restriction()
        for run in self:
            domain = [
                ('contract_id.date_end', '>=', run.date_start),
                ('contract_id.date_end', '<=', run.date_end),
            ]
            if run.branch_id:
                domain.append(('branch_id', '=', run.branch_id.id))
                
            employees = self.env['hr.employee'].with_context(active_test=False).search(domain)
            
            # Filter out employees already in the batch
            existing_employee_ids = run.slip_ids.mapped('employee_id').ids
            employees_to_add = employees.filtered(lambda e: e.id not in existing_employee_ids)
            
            slip_vals = []
            for emp in employees_to_add:
                slip_vals.append({
                    'run_id': run.id,
                    'employee_id': emp.id,
                    'termination_date': emp.contract_id.date_end,
                })
                
            if slip_vals:
                self.env['hr.termination.payslip'].create(slip_vals)
