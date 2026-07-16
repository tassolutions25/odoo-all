# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class HrResignationRun(models.Model):
    _name = 'hr.resignation.run'
    _description = 'Resignation Batch'
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

    slip_ids = fields.One2many('hr.resignation.payslip', 'run_id', string='Payslips')

    @api.model_create_multi
    def create(self, vals_list):
        self._check_manager_restriction()
        # Auto-assign branch if user has one (Branch Officer logic)
        user = self.env.user
        emp = user.employee_id
        
        for vals in vals_list:
            if not vals.get('branch_id') and emp and hasattr(emp, 'branch_id') and emp.branch_id:
                vals['branch_id'] = emp.branch_id.id
                
        return super(HrResignationRun, self).create(vals_list)

    def write(self, vals):
        if any(run.state == 'draft' for run in self):
            if not all(k in ['state', 'message_follower_ids', 'activity_ids', 'message_ids'] for k in vals.keys()):
                self._check_manager_restriction()
        return super(HrResignationRun, self).write(vals)

    def unlink(self):
        self._check_manager_restriction()
        return super(HrResignationRun, self).unlink()

    def _check_manager_restriction(self):
        """Helper to block Managers from Maker actions."""
        if self.env.user.has_group('payroll.group_payroll_manager'):
            if not self.env.user.has_group('base.group_system'):
                from odoo.exceptions import AccessError
                raise AccessError(_("Payroll Managers are restricted from this action (Create/Edit). This action is reserved for Payroll Officers."))

    def action_compute_sheet(self):
        for run in self:
            run.prepared_by_id = self.env.user.id
        for slip in self.slip_ids:
            slip.compute_sheet()
        self.state = 'calculated'

    def action_confirm(self):
        if not self.env.user.has_group('payroll.group_payroll_manager'):
             raise UserError(_("Only Payroll Managers can approve resignation batches."))
        for run in self:
            run.approved_by_id = self.env.user.id
        for slip in self.slip_ids:
            slip.action_confirm()
        self.state = 'done'
        # Generate Journal Entries
        self.generate_standalone_journal_entry()

    def action_print_excel(self):
        return {
            'type': 'ir.actions.act_url',
            'url': f'/ahadu_payroll/resignation_excel/{self.id}',
            'target': 'new',
        }

    def action_batch_upload(self):
        self.ensure_one()
        if self.state not in ['calculated', 'done']:
            raise UserError(_("You cannot generate the Batch Upload files until the resignation batch is Verified or Closed."))
            
        return {
            'type': 'ir.actions.act_url',
            'url': f'/ahadu_payroll/resignation_batch_upload/{self.id}',
            'target': 'new',
        }

    def generate_standalone_journal_entry(self):
        """
        Generates records in ahadu.journal.entry based on Resignation Batch.
        """
        self.ensure_one()
        JournalEntry = self.env['ahadu.journal.entry']
        JournalLine = self.env['ahadu.journal.entry.line']

        # 1. Create Header
        entry = JournalEntry.create({
            'name': f"Resignation Payroll Entry - {self.name}",
            'date': fields.Date.today(),
            'resignation_run_id': self.id,
            'state': 'posted',
        })

        slips = self.slip_ids.filtered(lambda s: s.state != 'cancel')
        journal_lines_to_create = []

        # Helper function to find ahadu.account
        def get_account(code):
            return self.env['ahadu.account'].search([('code', '=', code)], limit=1)

        # Pre-lookup common accounts to avoid queries in the loop
        acc_trans = get_account('5030204')
        acc_house = get_account('5030205')
        acc_mobile = get_account('5030221')
        acc_rep = get_account('5030206')
        acc_leave = get_account('2020217')
        acc_pension_comp_expense = get_account('5030211')
        acc_tax = get_account('2020301')
        acc_pension_payable = get_account('2020308')
        acc_sundries = get_account('4050011')
        acc_income_tax_payable_vat = get_account('2020305')
        acc_other_ded = get_account('4050012')
        acc_net_payable = get_account('2020300')

        for slip in slips:
            emp = slip.employee_id
            emp_type = emp.ahadu_employee_type_id.code or 'N/A'
            cost_center = slip.contract_id.cost_center_id or emp.contract_id.cost_center_id or emp.branch_id.cost_center_id
            if not cost_center:
                raise UserError(_(f"Employee {emp.name} has no Cost Center defined on contract or branch!"))

            # Basic Salary Account mapping (debit)
            basic_code = '5030101' if emp_type == 'CL_STAFF' else '5030102'
            acc_basic = get_account(basic_code)

            description = f"{emp.name} - Resignation Pay"

            # DEBITS (Earnings / Expenses)
            if slip.unpaid_salary > 0 and acc_basic:
                journal_lines_to_create.append({
                    'entry_id': entry.id,
                    'account_id': acc_basic.id,
                    'cost_center_id': cost_center.id,
                    'description': f"{description} - Basic Salary",
                    'debit': slip.unpaid_salary,
                    'credit': 0.0,
                })
            if slip.unpaid_transport > 0 and acc_trans:
                journal_lines_to_create.append({
                    'entry_id': entry.id,
                    'account_id': acc_trans.id,
                    'cost_center_id': cost_center.id,
                    'description': f"{description} - Transport Allowance",
                    'debit': slip.unpaid_transport,
                    'credit': 0.0,
                })
            if slip.unpaid_housing > 0 and acc_house:
                journal_lines_to_create.append({
                    'entry_id': entry.id,
                    'account_id': acc_house.id,
                    'cost_center_id': cost_center.id,
                    'description': f"{description} - Housing Allowance",
                    'debit': slip.unpaid_housing,
                    'credit': 0.0,
                })
            if slip.unpaid_mobile > 0 and acc_mobile:
                journal_lines_to_create.append({
                    'entry_id': entry.id,
                    'account_id': acc_mobile.id,
                    'cost_center_id': cost_center.id,
                    'description': f"{description} - Mobile Allowance",
                    'debit': slip.unpaid_mobile,
                    'credit': 0.0,
                })
            if slip.representation_allowance > 0 and acc_rep:
                journal_lines_to_create.append({
                    'entry_id': entry.id,
                    'account_id': acc_rep.id,
                    'cost_center_id': cost_center.id,
                    'description': f"{description} - Representation Allowance",
                    'debit': slip.representation_allowance,
                    'credit': 0.0,
                })
            if slip.leave_pay_gross > 0 and acc_leave:
                journal_lines_to_create.append({
                    'entry_id': entry.id,
                    'account_id': acc_leave.id,
                    'cost_center_id': cost_center.id,
                    'description': f"{description} - Leave Pay Gross",
                    'debit': slip.leave_pay_gross,
                    'credit': 0.0,
                })
            if slip.pension_comp > 0 and acc_pension_comp_expense:
                journal_lines_to_create.append({
                    'entry_id': entry.id,
                    'account_id': acc_pension_comp_expense.id,
                    'cost_center_id': cost_center.id,
                    'description': f"{description} - Pension Comp Expense (11%)",
                    'debit': slip.pension_comp,
                    'credit': 0.0,
                })

            # CREDITS (Deductions / Payables)
            if slip.grand_tax > 0 and acc_tax:
                journal_lines_to_create.append({
                    'entry_id': entry.id,
                    'account_id': acc_tax.id,
                    'cost_center_id': cost_center.id,
                    'description': f"{description} - Income Tax",
                    'debit': 0.0,
                    'credit': slip.grand_tax,
                })
            
            pension_total = slip.pension_emp + slip.pension_comp
            if pension_total > 0 and acc_pension_payable:
                journal_lines_to_create.append({
                    'entry_id': entry.id,
                    'account_id': acc_pension_payable.id,
                    'cost_center_id': cost_center.id,
                    'description': f"{description} - Pension Payable (18%)",
                    'debit': 0.0,
                    'credit': pension_total,
                })

            if slip.lost_id_card > 0 and acc_sundries:
                journal_lines_to_create.append({
                    'entry_id': entry.id,
                    'account_id': acc_sundries.id,
                    'cost_center_id': cost_center.id,
                    'description': f"{description} - Lost ID Card",
                    'debit': 0.0,
                    'credit': slip.lost_id_card,
                })

            if slip.vat_on_id_card > 0 and acc_income_tax_payable_vat:
                journal_lines_to_create.append({
                    'entry_id': entry.id,
                    'account_id': acc_income_tax_payable_vat.id,
                    'cost_center_id': cost_center.id,
                    'description': f"{description} - VAT on ID Card",
                    'debit': 0.0,
                    'credit': slip.vat_on_id_card,
                })

            if slip.other_deductions > 0 and acc_other_ded:
                journal_lines_to_create.append({
                    'entry_id': entry.id,
                    'account_id': acc_other_ded.id,
                    'cost_center_id': cost_center.id,
                    'description': f"{description} - Other Deductions",
                    'debit': 0.0,
                    'credit': slip.other_deductions,
                })

            if slip.net_payable > 0 and acc_net_payable:
                journal_lines_to_create.append({
                    'entry_id': entry.id,
                    'account_id': acc_net_payable.id,
                    'cost_center_id': cost_center.id,
                    'description': f"{description} - Net Salary Payable",
                    'debit': 0.0,
                    'credit': slip.net_payable,
                })

        if journal_lines_to_create:
            JournalLine.create(journal_lines_to_create)

        return True

    def action_cancel(self):
        for slip in self.slip_ids:
            slip.action_cancel()
        self.state = 'cancel'
        
    def action_draft(self):
        if any(run.state == 'done' for run in self):
            raise UserError(_("This resignation batch is already Done/Approved. You cannot reset it to Draft."))
        self.write({
            'state': 'draft',
            'bank_transfer_done': False
        })

    def action_generate_payslips(self):
        self._check_manager_restriction()
        skipped_names = []
        for run in self:
            # 1. Fetch employees with approved resignation record in range
            resignation_records = self.env['hr.employee.resignation'].search([
                ('resignation_date', '>=', run.date_start),
                ('resignation_date', '<=', run.date_end),
                ('state', 'in', ['approved', 'Approved'])
            ])
            res_employees = resignation_records.mapped('employee_id')

            # 2. Fetch employees with contract end date in range
            domain_contract = [
                ('contract_id.date_end', '>=', run.date_start),
                ('contract_id.date_end', '<=', run.date_end),
            ]
            contract_employees = self.env['hr.employee'].with_context(active_test=False).search(domain_contract)
            
            employees = res_employees | contract_employees

            if run.branch_id:
                employees = employees.filtered(lambda e: e.branch_id.id == run.branch_id.id)
                
            # Filter out employees already in the batch
            existing_employee_ids = run.slip_ids.mapped('employee_id').ids
            candidates = employees.filtered(lambda e: e.id not in existing_employee_ids)

            settled_resignation_employee_ids = self.env['hr.resignation.payslip'].search([
                ('employee_id', 'in', candidates.ids),
                '|', ('is_settled', '=', True), ('state', '=', 'done'),
            ]).mapped('employee_id').ids
            settled_termination_employee_ids = self.env['hr.termination.payslip'].search([
                ('employee_id', 'in', candidates.ids),
                '|', ('is_settled', '=', True), ('state', '=', 'done'),
            ]).mapped('employee_id').ids
            settled_employee_ids = set(settled_resignation_employee_ids + settled_termination_employee_ids)

            skipped = candidates.filtered(lambda e: e.id in settled_employee_ids)
            skipped_names.extend(skipped.mapped('name'))
            employees_to_add = candidates.filtered(lambda e: e.id not in settled_employee_ids)
            
            slip_vals = []
            for emp in employees_to_add:
                # Find correct resignation date
                res_rec = resignation_records.filtered(lambda r: r.employee_id.id == emp.id)
                if res_rec:
                    res_date = res_rec[0].resignation_date
                else:
                    res_date = emp.contract_id.date_end

                slip_vals.append({
                    'run_id': run.id,
                    'employee_id': emp.id,
                    'resignation_date': res_date,
                })
                
            if slip_vals:
                self.env['hr.resignation.payslip'].create(slip_vals)

            if skipped:
                run.message_post(body=_("Skipped already settled employees: %s") % ", ".join(skipped.mapped('name')))

        if skipped_names:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Already Settled'),
                    'message': _('Skipped already settled employees: %s') % ", ".join(sorted(set(skipped_names))),
                    'type': 'warning',
                    'sticky': False,
                }
            }
