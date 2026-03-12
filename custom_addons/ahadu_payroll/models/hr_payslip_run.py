# -*- coding: utf-8 -*-
import time
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    state = fields.Selection([
        ('draft', 'Draft'),
        ('verify', 'To Verify'),
        ('close', 'Done'),
    ], string='Status', index=True, readonly=True, copy=False, default='draft')

    pay_group_ids = fields.Many2many(
        'ahadu.pay.group',
        string='Pay Groups',
        help="Optional: Filter payslips by pay group. Leave empty to include all employees."
    )

    cost_center_ids = fields.Many2many(
        'hr.cost.center',
        string='Cost Centers',
        help="Optional: Filter payslips by Cost Center. Leave empty to include all."
    )

    branch_ids = fields.Many2many(
        'hr.branch',
        'hr_payslip_run_branch_rel',
        'payslip_run_id',
        'branch_id',
        string='Branches (Filter)',
        help="Optional: Filter payslips by Branch. Leave empty to include all branches."
    )

    region_ids = fields.Many2many(
        'hr.region',
        string='Regions',
        help="Optional: Filter payslips by Region. Leave empty to include all regions."
    )

    department_ids = fields.Many2many(
        'hr.department',
        string='Departments',
        help="Optional: Filter payslips by Department. Leave empty to include all."
    )


    branch_id = fields.Many2one(
        'hr.branch',
        string='Branch',
        help="Specific Branch for this payroll run. Required for Branch Officers."
    )


    # Computed field that returns slip_ids filtered by selected pay groups
    filtered_slip_ids = fields.One2many(
        'hr.payslip',
        compute='_compute_filtered_slip_ids',
        string='Filtered Payslips',
        help="Payslips filtered by selected pay groups"
    )

    # Computed field showing employees available in selected pay groups
    available_employee_ids = fields.Many2many(
        'hr.employee',
        compute='_compute_available_employees',
        string='Available Employees',
        help="Employees with active contracts in the selected pay groups"
    )

    employee_count = fields.Integer(
        compute='_compute_available_employees',
        string='Employee Count'
    )

    slip_ids_domain = fields.Binary(compute='_compute_slip_ids_domain')

    # --- TRACKING FIELDS ---
    created_by_id = fields.Many2one(
        'res.users', 
        string='Created By', 
        default=lambda self: self.env.user,
        readonly=True,
        copy=False
    )
    
    approved_by_id = fields.Many2one(
        'res.users', 
        string='Approved By', 
        readonly=True,
        copy=False
    )
    
    approved_date = fields.Datetime(
        string='Approved On', 
        readonly=True,
        copy=False
    )

    bank_transfer_done = fields.Boolean(
        string='Bank Transfer Done', 
        default=False, 
        copy=False,
        readonly=True,
        help="Technical field to track if bank transfer was executed."
    )
    
    cash_indemnity_done = fields.Boolean(
        string='Cash Indemnity Done', 
        default=False, 
        copy=False,
        readonly=True,
        help="Technical field to track if cash indemnity bank transfer was executed."
    )

    @api.model_create_multi
    def create(self, vals_list):
        """
        Restrict Payroll Managers from creating payslip batches.
        Only Payroll Officers or System Administrators should create.
        Also auto-assign branch if user has a branch.
        """
        # Auto-assign branch if user is restricted (Branch Payroll Group)
        # We assume if they have a branch, they are restricted, unless they are Head Office.
        # But explicit check is better. For now, defaulting to employee's branch is safe.
        user = self.env.user
        emp = user.employee_id
        
        for vals in vals_list:
            if not vals.get('branch_id') and emp and hasattr(emp, 'branch_id') and emp.branch_id:
                # If user is Head Office, they might want empty branch. 
                # But if they are Branch Officer, they MUST have branch.
                # Use Record Rules to enforce "Must be my branch". 
                # Here we just default to help them.
                vals['branch_id'] = emp.branch_id.id

        # Check if user is a Payroll Manager
        self._check_manager_restriction()
                
        return super(HrPayslipRun, self).create(vals_list)

    @api.depends('pay_group_ids', 'cost_center_ids', 'branch_ids', 'region_ids', 'slip_ids', 'slip_ids.contract_id.pay_group_id', 'slip_ids.contract_id.cost_center_id', 'slip_ids.employee_id.branch_id', 'slip_ids.employee_id.region_id')
    def _compute_filtered_slip_ids(self):
        """Filter slip_ids by the selected pay groups, cost centers, branches, and regions."""
        for batch in self:
            slips = batch.slip_ids
            
            # 1. Filter by Pay Group
            if batch.pay_group_ids:
                slips = slips.filtered(lambda s: s.contract_id.pay_group_id in batch.pay_group_ids)
            
            # 2. Filter by Cost Center
            if batch.cost_center_ids:
                slips = slips.filtered(lambda s: s.contract_id.cost_center_id in batch.cost_center_ids)
            
            # 3. Filter by Branch
            if batch.branch_ids:
                slips = slips.filtered(lambda s: s.employee_id.branch_id in batch.branch_ids)
            
            # 4. Filter by Region
            if batch.region_ids:
                slips = slips.filtered(lambda s: s.employee_id.region_id in batch.region_ids)
            
            # 5. Filter by Department
            if batch.department_ids:
                all_dept_ids = self.env['hr.department'].search([('id', 'child_of', batch.department_ids.ids)]).ids
                slips = slips.filtered(lambda s: s.employee_id.department_id.id in all_dept_ids)
            
                
            batch.filtered_slip_ids = slips

    # ... existing methods ...


    @api.depends('pay_group_ids', 'cost_center_ids', 'branch_ids', 'region_ids', 'department_ids')
    def _compute_available_employees(self):
        """Find all employees matching the selected criteria (hierarchical department, branch, region, etc)."""
        Employee = self.env['hr.employee']
        for batch in self:
            if not (batch.pay_group_ids or batch.cost_center_ids or batch.branch_ids or batch.region_ids or batch.department_ids):
                batch.available_employee_ids = self.env['hr.employee']
                batch.employee_count = 0
                continue

            # 1. Start with Employee-level criteria
            emp_domain = []
            if batch.department_ids:
                emp_domain.append(('department_id', 'child_of', batch.department_ids.ids))
            if batch.branch_ids:
                emp_domain.append(('branch_id', 'in', batch.branch_ids.ids))
            if batch.region_ids:
                emp_domain.append(('region_id', 'in', batch.region_ids.ids))

            employees = Employee.search(emp_domain) if emp_domain else Employee.search([])

            # 2. Filter by Contract-level criteria (Pay Group / Cost Center)
            # We only consider employees with 'open' contracts for these filters.
            if batch.pay_group_ids or batch.cost_center_ids:
                contract_domain = [('state', '=', 'open')]
                if batch.pay_group_ids:
                    contract_domain.append(('pay_group_id', 'in', batch.pay_group_ids.ids))
                if batch.cost_center_ids:
                    contract_domain.append(('cost_center_id', 'in', batch.cost_center_ids.ids))
                
                # Further restrict to current set of matching employees
                contract_domain.append(('employee_id', 'in', employees.ids))
                contracts = self.env['hr.contract'].search(contract_domain)
                employees = contracts.mapped('employee_id')

            batch.available_employee_ids = employees
            batch.employee_count = len(employees)

    @api.depends('pay_group_ids', 'cost_center_ids', 'branch_ids', 'region_ids', 'department_ids')
    def _compute_slip_ids_domain(self):
        """Compute domain for slip_ids based on selected pay groups, cost centers, branches, and regions."""
        for batch in self:
            domain = []
            if batch.pay_group_ids:
                domain.append(('contract_id.pay_group_id', 'in', batch.pay_group_ids.ids))
            if batch.cost_center_ids:
                domain.append(('contract_id.cost_center_id', 'in', batch.cost_center_ids.ids))
            if batch.branch_ids:
                domain.append(('employee_id.branch_id', 'in', batch.branch_ids.ids))
            if batch.region_ids:
                domain.append(('employee_id.region_id', 'in', batch.region_ids.ids))
            if batch.department_ids:
                domain.append(('employee_id.department_id', 'child_of', batch.department_ids.ids))
            
            batch.slip_ids_domain = domain

    @api.model
    def _check_manager_restriction(self):
        """
        Helper validation to block Managers from executing operational actions.
        Raises AccessError if user is a Manager but not a System Admin.
        """
        # Check if user is a Payroll Manager
        if self.env.user.has_group('payroll.group_payroll_manager'):
            # Check if user is NOT a System Admin (Superuser)
            if not self.env.user.has_group('base.group_system'):
                from odoo.exceptions import AccessError
                raise AccessError(_("Payroll Managers are restricted from this action (Create/Process). This action is reserved for Payroll Officers."))

    def action_generate_payslips_filtered(self):
        """
        Generate payslips for all employees matching the selected filters (Pay Group / Cost Center / Branch / Region).
        Restricted for Managers.
        """
        self._check_manager_restriction()
        self.ensure_one()
        
        if not self.pay_group_ids and not self.cost_center_ids and not self.branch_ids and not self.region_ids and not self.department_ids:
            raise UserError(_("Please select at least one Pay Group, Cost Center, Branch, Region, or Department to generate payslips."))
        
        Payslip = self.env['hr.payslip']
        Contract = self.env['hr.contract']
        
        # Get the salary structure (use default if available)
        structure = self.env.ref('ahadu_payroll.structure_ahadu_monthly', raise_if_not_found=False)
        if not structure:
            # Fallback: get the first available structure
            structure = self.env['hr.payroll.structure'].search([], limit=1)
        
        if not structure:
            raise UserError(_("No salary structure found. Please create a salary structure first."))
        
        # Build Domain for Fetching Contracts for the matching employees
        # We start with the same logic as _compute_available_employees
        emp_domain = []
        if self.department_ids:
            emp_domain.append(('department_id', 'child_of', self.department_ids.ids))
        if self.branch_ids:
            emp_domain.append(('branch_id', 'in', self.branch_ids.ids))
        if self.region_ids:
            emp_domain.append(('region_id', 'in', self.region_ids.ids))

        employees = self.env['hr.employee'].search(emp_domain) if emp_domain else self.env['hr.employee'].search([])

        # Now get active contracts for these employees, matching pay_group/cost_center if selected
        contract_domain = [('state', '=', 'open'), ('employee_id', 'in', employees.ids)]
        if self.pay_group_ids:
            contract_domain.append(('pay_group_id', 'in', self.pay_group_ids.ids))
        if self.cost_center_ids:
            contract_domain.append(('cost_center_id', 'in', self.cost_center_ids.ids))

        # Find active contracts
        contracts = Contract.search(contract_domain)
        
        if not contracts:
            raise UserError(_("No active contracts found for the selected criteria."))
        
        # Get employees who already have payslips in this batch
        existing_employee_ids = self.slip_ids.mapped('employee_id').ids
        
        # Filter contracts to exclude employees who already have payslips
        new_contracts = contracts.filtered(
            lambda c: c.employee_id.id not in existing_employee_ids
        )
        
        # --- EXCLUDE TERMINATED EMPLOYEES ---
        # Fetch employees who have a Termination Payslip in this period
        terminated_slips = self.env['hr.termination.payslip'].search([
            ('termination_date', '>=', self.date_start),
            ('termination_date', '<=', self.date_end),
            ('state', '!=', 'cancel')
        ])
        terminated_emp_ids = terminated_slips.mapped('employee_id').ids
        if terminated_emp_ids:
             new_contracts = new_contracts.filtered(lambda c: c.employee_id.id not in terminated_emp_ids)
             _logger.info(f"Excluded {len(terminated_emp_ids)} terminated employees from batch {self.name}")

        if not new_contracts:
            raise UserError(_("All employees in the selected filters already have payslips in this batch (or are terminated)."))
        
        # --- DUPLICATE EMPLOYEE ID CHECK ---
        # The user's field for employee id in ahadu_hr is 'employee_id'
        emp_ids = new_contracts.mapped('employee_id.employee_id')
        seen = set()
        duplicates = set()
        for eid in emp_ids:
            if not eid: continue
            if eid in seen:
                duplicates.add(eid)
            seen.add(eid)
        
        if duplicates:
            dup_names = new_contracts.filtered(lambda c: c.employee_id.employee_id in duplicates).mapped('employee_id.name')
            raise UserError(_("Duplicate Employee IDs detected in the selection: %s (%s). Manual correction is required before batch generation.") % (", ".join(duplicates), ", ".join(dup_names)))
        
        # Create payslips for each contract
        payslips_created = 0
        new_payslips = self.env['hr.payslip']
        for contract in new_contracts:
            payslip_vals = {
                'employee_id': contract.employee_id.id,
                'contract_id': contract.id,
                'struct_id': structure.id,
                'date_from': self.date_start,
                'date_to': self.date_end,
                'payslip_run_id': self.id,
                'name': f"Salary Slip - {contract.employee_id.name} - {self.name}",
            }
            payslip = Payslip.create(payslip_vals)
            new_payslips += payslip
            payslips_created += 1
        
        # Compute all newly created payslips explicitly
        # This triggers the calculation of salary rules (Basic, Tax, Net, etc.)
        if new_payslips:
            new_payslips.compute_sheet()
        
        _logger.info(f"Generated and computed {payslips_created} payslips for filtered batch '{self.name}'")
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Payslips Generated'),
                'message': _(f'{payslips_created} payslips created and computed successfully.'),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_verify(self):
        """
        Officer submits for verification.
        Auto-generates payslips if filters are selected but no payslips exist yet.
        """
        self.ensure_one()
        
        payslips_created = 0
        
        # Check if filters are selected (Pay Group, Cost Center, Branch, Region, or Department)
        if self.pay_group_ids or self.cost_center_ids or self.branch_ids or self.region_ids or self.department_ids:
            # Check if there are any payslips for the selected filters
            if not self.filtered_slip_ids:
                # Auto-generate payslips
                _logger.info(f"Auto-generating payslips for batch '{self.name}' before verification")
                
                try:
                    # Call the generation logic (reuse existing method logic)
                    Payslip = self.env['hr.payslip']
                    Contract = self.env['hr.contract']
                    
                    # Get the salary structure
                    structure = self.env.ref('ahadu_payroll.structure_ahadu_monthly', raise_if_not_found=False)
                    if not structure:
                        structure = self.env['hr.payroll.structure'].search([], limit=1)
                    
                    if not structure:
                        raise UserError(_("No salary structure found. Please create a salary structure first."))
                    
                    # Build Domain for Fetching Contracts (Same as above)
                    emp_domain = []
                    if self.department_ids:
                        emp_domain.append(('department_id', 'child_of', self.department_ids.ids))
                    if self.branch_ids:
                        emp_domain.append(('branch_id', 'in', self.branch_ids.ids))
                    if self.region_ids:
                        emp_domain.append(('region_id', 'in', self.region_ids.ids))

                    employees = self.env['hr.employee'].search(emp_domain) if emp_domain else self.env['hr.employee'].search([])

                    contract_domain = [('state', '=', 'open'), ('employee_id', 'in', employees.ids)]
                    if self.pay_group_ids:
                        contract_domain.append(('pay_group_id', 'in', self.pay_group_ids.ids))
                    if self.cost_center_ids:
                        contract_domain.append(('cost_center_id', 'in', self.cost_center_ids.ids))

                    # Find active contracts
                    contracts = Contract.search(contract_domain)
                    
                    if not contracts:
                        raise UserError(_("No active contracts found for the selected criteria."))
                    
                    # Get employees who already have payslips in this batch
                    existing_employee_ids = self.slip_ids.mapped('employee_id').ids
                    
                    # Filter contracts to exclude employees who already have payslips
                    new_contracts = contracts.filtered(
                        lambda c: c.employee_id.id not in existing_employee_ids
                    )
                    
                    # Exclude terminated employees
                    terminated_slips = self.env['hr.termination.payslip'].search([
                        ('termination_date', '>=', self.date_start),
                        ('termination_date', '<=', self.date_end),
                        ('state', '!=', 'cancel')
                    ])
                    terminated_emp_ids = terminated_slips.mapped('employee_id').ids
                    if terminated_emp_ids:
                        new_contracts = new_contracts.filtered(lambda c: c.employee_id.id not in terminated_emp_ids)
                    
                    if new_contracts:
                        # Create payslips for each contract
                        new_payslips = self.env['hr.payslip']
                        for contract in new_contracts:
                            payslip_vals = {
                                'employee_id': contract.employee_id.id,
                                'contract_id': contract.id,
                                'struct_id': structure.id,
                                'date_from': self.date_start,
                                'date_to': self.date_end,
                                'payslip_run_id': self.id,
                                'name': f"Salary Slip - {contract.employee_id.name} - {self.name}",
                            }
                            payslip = Payslip.create(payslip_vals)
                            new_payslips += payslip
                            payslips_created += 1
                        
                        # Compute all newly created payslips
                        if new_payslips:
                            new_payslips.compute_sheet()
                        
                        _logger.info(f"Auto-generated {payslips_created} payslips for batch '{self.name}'")
                    
                except Exception as e:
                    _logger.error(f"Failed to auto-generate payslips for batch '{self.name}': {str(e)}")
                    raise UserError(_(f"Failed to auto-generate payslips: {str(e)}"))
        
        # Proceed with state change
        self.write({'state': 'verify'})
        
        # Show notification if payslips were auto-generated
        if payslips_created > 0:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Payslips Auto-Generated'),
                    'message': _(f'{payslips_created} payslips were automatically generated for the selected filters.'),
                    'type': 'success',
                    'sticky': False,
                }
            }

    def action_draft(self):
        """Manager can reset to draft."""
        if self.state == 'close':
            raise UserError(_("This batch is already Approved & Closed. You cannot reset it to Draft."))
        self.write({'state': 'draft'})

    def close_payslip_run(self):
        """
        Override the standard close action to:
        1. Generate Standalone Journal Entries.
        2. Set all Payslips to 'Done'.
        3. Track Approver.
        """
        for batch in self:
            if batch.state == 'verify':
                # 1. Generate Journal Entries
                batch.generate_standalone_journal_entry()
                
                # 2. Confirm all Payslips (Set to Done)
                slips_to_confirm = batch.slip_ids.filtered(lambda s: s.state in ['draft', 'verify'])
                if slips_to_confirm:
                    for slip in slips_to_confirm:
                        slip.action_payslip_done()
                        
                # 3. Track Approval
                batch.write({
                    'approved_by_id': self.env.user.id,
                    'approved_date': fields.Datetime.now()
                })
                # 4. Automatically send Payslips to Employees via Email
                batch.slip_ids.sudo().action_send_payslip_email()
        
        # Call the standard method to handle state change (if any) or just write state
        return self.write({'state': 'close'})

    def generate_standalone_journal_entry(self):
        """
        Generates records in ahadu.journal.entry based on Scenarios 1, 2, and 3.
        OPTIMIZED: Uses batch create for all journal lines to improve performance.
        """
        start_time = time.time()
        self.ensure_one()
        
        JournalEntry = self.env['ahadu.journal.entry']
        JournalLine = self.env['ahadu.journal.entry.line']

        # 1. Create the Header
        entry = JournalEntry.create({
            'name': f"Payroll Entry - {self.name}",
            'date': fields.Date.today(),
            'payslip_run_id': self.id,
            'state': 'posted',
        })
        # 2. OPTIMIZATION: Collect all journal lines in a list for batch creation
        journal_lines_to_create = []
        
        # 3. Loop through every Payslip in this Batch
        for slip in self.slip_ids:
            
            # Skip cancelled slips
            if slip.state == 'cancel':
                continue

            employee_cc = slip.contract_id.cost_center_id
            if not employee_cc:
                raise UserError(_(f"Contract for {slip.employee_id.name} has no Cost Center defined!"))

            # 4. Loop through the Calculation Lines (Salary Rules)
            for line in slip.line_ids:
                amount = line.total
                if amount == 0:
                    continue

                # Get the accounts from the Salary Rule
                rule = line.salary_rule_id
                debit_account = rule.ahadu_debit_account_id
                credit_account = rule.ahadu_credit_account_id

                description = f"{slip.employee_id.name} - {line.name}"
                
                # --- SIGN HANDLING LOGIC ---
                # If amount is negative (e.g. Penalty), we swap the lines:
                # Debit account becomes Credit, Credit account becomes Debit.
                if amount > 0:
                    d_acc, c_acc = debit_account, credit_account
                else:
                    d_acc, c_acc = credit_account, debit_account
                
                abs_amount = abs(amount)

                # --- GENERATE DEBIT LINE ---
                if d_acc:
                    journal_lines_to_create.append({
                        'entry_id': entry.id,
                        'account_id': d_acc.id,
                        'cost_center_id': employee_cc.id,
                        'description': description,
                        'debit': abs_amount,
                        'credit': 0.0,
                    })

                # --- GENERATE CREDIT LINE ---
                if c_acc:
                    journal_lines_to_create.append({
                        'entry_id': entry.id,
                        'account_id': c_acc.id,
                        'cost_center_id': employee_cc.id,
                        'description': description,
                        'debit': 0.0,
                        'credit': abs_amount,
                    })
        
        # 5. Single batch create for all journal lines
        if journal_lines_to_create:
            JournalLine.create(journal_lines_to_create)
        
        # 6. Performance logging
        elapsed = time.time() - start_time
        slip_count = len(self.slip_ids.filtered(lambda s: s.state != 'cancel'))
        _logger.info(
            f"Journal entry for batch '{self.name}': {len(journal_lines_to_create)} lines "
            f"created in {elapsed:.2f}s ({slip_count} payslips, "
            f"{elapsed/slip_count if slip_count else 0:.3f}s per slip)"
        )
        
        return True
    
    def action_print_bank_transfer(self):
        """Returns a URL action to download the Excel file."""
        self.ensure_one()
        if self.state != 'close':
            raise UserError(_("You cannot generate the Bank Transfer File until the payroll batch is Approved and Closed."))
        if self.bank_transfer_done:
            raise UserError(_("The Bank Transfer has already been processed for this batch. You cannot pay twice."))
            
        return {
            'type': 'ir.actions.act_url',
            'url': f'/ahadu_payroll/bank_transfer/{self.id}',
            'target': 'new',
        }
    
    def action_print_pension_report(self):
        """Download Pension Excel."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/ahadu_payroll/pension_report/{self.id}',
            'target': 'new',
        }

    def action_print_tax_report(self):
        """Download Tax Report Excel (Form No. 1103)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/ahadu_payroll/tax_declaration/{self.id}',
            'target': 'new',
        }

    def action_print_tax_declaration(self):
        """Download Tax Declaration Form (Alternate or As-Is)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/ahadu_payroll/tax_declaration/{self.id}',
            'target': 'new',
        }

    def action_print_payroll_sheet_excel(self):
        """Download Master Payroll Sheet Excel."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/ahadu_payroll/payroll_sheet_excel/{self.id}',
            'target': 'new',
        }

    def action_print_cost_sharing_report(self):
        """Download Education Cost Sharing Report Excel (Focused)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/ahadu_payroll/cost_sharing_excel/{self.id}',
            'target': 'new',
        }
        
    def action_print_cash_indemnity_report(self):
        """Download Cash Indemnity Excel Report."""
        self.ensure_one()
        if self.state != 'close':
            raise UserError(_("The bank transfer cannot be performed on unfinished or unverified and unapproved payrolls."))
            
        return {
            'type': 'ir.actions.act_url',
            'url': f'/ahadu_payroll/cash_indemnity_report/{self.id}',
            'target': 'new',
        }
