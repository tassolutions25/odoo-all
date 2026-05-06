from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import logging

_logger = logging.getLogger(__name__)

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    # ====================
    # SIMPLE PAYROLL FIELDS
    # ====================
    
    # Current Salary from Contract
    current_salary = fields.Monetary(
        string='Current Basic Salary',
        compute='_compute_current_salary',
        currency_field='currency_id',
        help="Current basic salary from active contract"
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )

    # Payslip Count
    payslip_count = fields.Integer(
        string='Total Payslips',
        compute='_compute_payslip_count'
    )
    
    # Deduction Count
    deduction_count = fields.Integer(
        string='Active Deductions',
        compute='_compute_deduction_count'
    )
    
    # Deductions - One2many for tab view
    deduction_ids = fields.One2many(
        'hr.employee.deduction',
        'employee_id',
        string='Deductions'
    )
    
    # Loans - One2many for tab view
    loan_ids = fields.One2many(
        'hr.loan',
        'employee_id',
        string='Loans'
    )

    cif = fields.Char(string='CIF', help="Customer Information File - Unique Identifier")
    
    @api.depends('emp_wage')
    def _compute_current_salary(self):
        """Get current salary from employee wage field (from ahadu.hr module)."""
        for employee in self:
            # Use emp_wage from custom ahadu.hr module
            if hasattr(employee, 'emp_wage'):
                employee.current_salary = employee.emp_wage or 0.0
            else:
                employee.current_salary = 0.0
    
    def _compute_payslip_count(self):
        """Count payslips for this employee."""
        for employee in self:
            employee.payslip_count = self.env['hr.payslip'].search_count([
                ('employee_id', '=', employee.id)
            ])
    
    def _compute_deduction_count(self):
        """Count active deductions for this employee."""
        for employee in self:
            employee.deduction_count = self.env['hr.employee.deduction'].search_count([
                ('employee_id', '=', employee.id),
                ('state', '=', 'active')
            ])
    
    def action_view_payslips(self):
        """Action to view all payslips for this employee."""
        self.ensure_one()
        return {
            'name': 'My Payslips',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payslip',
            'view_mode': 'tree,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }

    def _extract_cif_from_salary_account(self):
        """
        Extracts CIF from the first salary account number by dropping the last 5 digits 
        and stripping leading zeros.
        Example: '0000021410101' -> '214'
        """
        self.ensure_one()
        salary_account = self.bank_account_ids.filtered(lambda a: a.account_type == 'salary')[:1]
        if not salary_account or not salary_account.account_number:
            return False
            
        acc_no = salary_account.account_number.strip()
        if len(acc_no) <= 5:
            return False
            
        # Drop last 5 digits
        prefix = acc_no[:-5]
        # Strip leading zeros
        cif_str = prefix.lstrip('0')
        
        return cif_str or False

    def action_fetch_cif(self):
        """Fetch CIF number manually from linked salary bank accounts."""
        self.ensure_one()
        cif_val = self._extract_cif_from_salary_account()
        if cif_val:
            self.cif = cif_val
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('CIF %s successfully extracted from salary account.') % cif_val,
                    'sticky': False,
                    'type': 'success',
                }
            }
        else:
            raise UserError(_("Could not extract CIF. Ensure the employee has a 'Salary' bank account with a valid 13-digit number."))

    def _fetch_cif_from_api(self, mobile_phone, account_no):
        """
        Helper to fetch CIF from API. 
        Returns (cif_value, error_message)
        """
        # Clean phone number: remove spaces and leading '+'
        phone = (mobile_phone or "").strip().replace(' ', '')
        if phone.startswith('+'):
            phone = phone[1:]
        
        # Ensure it starts with 251
        if phone.startswith('0'):
            phone = '251' + phone[1:]
        elif phone.startswith('9') or phone.startswith('7'):
            phone = '251' + phone
            
        url = "https://10.20.1.22:8243/get-cif/1.0.0/get-cif"
        headers = {
            'accept': '*/*',
            'Content-Type': 'application/json'
        }
        
        payload = {
            "mobileNo": phone,
            "AccountNum": account_no
        }
        
        # Debug logging to file
        import os
        import json
        debug_file = os.path.join(os.path.dirname(__file__), 'cif_api_debug.json')
        
        try:
            # We use verify=False because it's an internal IP/HTTPS which might have self-signed certs
            response = requests.post(url, json=payload, headers=headers, verify=False, timeout=10)
            
            # Dump response to file for inspection
            with open(debug_file, 'w') as f:
                json.dump({
                    'status': response.status_code,
                    'text': response.text,
                    'payload': payload,
                    'url': url
                }, f)
            
            response.raise_for_status()
            data = response.json()
            
            if isinstance(data, dict):
                cif_val = data.get('cif') or data.get('CIF') or data.get('value') or data.get('customerNo') or data.get('customer_no')
            else:
                cif_val = data
            
            if cif_val:
                try:
                    return int(cif_val), False
                except (ValueError, TypeError):
                    return False, _("API returned invalid format: %s") % cif_val
            else:
                return False, _("No CIF data found for this combo.")

        except requests.exceptions.RequestException as e:
            # Catching connection errors specifically
            return False, _("Connection failed")
        except Exception as e:
            return False, _("Unexpected error")

    @api.model
    def cron_fetch_cif(self):
        """Scheduled action to fetch CIF for all employees missing it by extracting from salary accounts."""
        # Find employees where CIF is not set
        domain = [
            '|', ('cif', '=', False), ('cif', '=', ''),
        ]
        employees = self.search(domain)
        
        _logger.info("CIF_SYNC: Starting automated fetch. Found %s employees to process.", len(employees))
        
        if not employees:
            _logger.info("CIF_SYNC: No employees found matching the criteria.")
            return

        count = 0
        for emp in employees:
            cif_val = emp._extract_cif_from_salary_account()
            if cif_val:
                emp.cif = cif_val
                count += 1
                _logger.info("CIF_SYNC: Successfully extracted CIF %s for %s", cif_val, emp.name)
            
            # Commit periodically
            if count % 20 == 0 and count > 0:
                self.env.cr.commit()
                
        _logger.info("CIF_SYNC: Finished automated CIF fetch. Successfully updated %s records.", count)

    def action_sync_loans(self):
        """Manual trigger for loan sync."""
        self.ensure_one()
        if not self.cif:
            raise UserError(_("Employee must have a CIF number to sync loans."))
        
        count, errors = self._sync_external_loans()
        if errors:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sync Completed with Errors'),
                    'message': _('Synced %s loans. Errors: %s') % (count, ", ".join(errors)),
                    'type': 'warning',
                    'sticky': True,
                }
            }
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Successfully synced %s loans.') % count,
                'type': 'success',
                'sticky': False,
            }
        }

    def _sync_external_loans(self):
        """
        Fetches loans from the external API for this employee.
        Returns (count_synced, error_messages)
        """
        self.ensure_one()
        url = "http://10.1.11.11:7024/api/loandata"
        payload = {"id": str(self.cif)}
        headers = {'Content-Type': 'application/json'}
        
        errors = []
        synced_count = 0
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if not isinstance(data, list):
                return 0, [_("API returned unexpected data format.")]

            Loan = self.env['hr.loan']
            LoanType = self.env['hr.loan.type']
            BankAccount = self.env['hr.employee.bank.account']
            
            for loan_data in data:
                ref = loan_data.get('loanReference')
                if not ref:
                    continue
                
                # 1. Map or Create Loan Type
                product_name = loan_data.get('loanProduct') or loan_data.get('loanType') or 'Unknown Loan'
                loan_type = LoanType.search([
                    '|', ('api_product_code', '=', product_name), 
                    ('name', '=', product_name)
                ], limit=1)
                
                if not loan_type:
                    # Automatically create the loan type if it doesn't exist
                    loan_type = LoanType.create({
                        'name': product_name,
                        'api_product_code': product_name,
                        'bank_account_type': 'loan_settlement',
                    })
                    _logger.info("LOAN_SYNC: Created new Loan Type '%s'", product_name)

                # 2. Extract Values
                status = loan_data.get('status')
                installment = float(loan_data.get('monthlyInstallment') or 0.0)
                remaining = float(loan_data.get('remainingAmount') or 0.0)
                requested = float(loan_data.get('requestedAmount') or 0.0)
                acc_no = loan_data.get('accountNumber')
                
                # 3. Handle Bank Account
                bank_acc = False
                if acc_no:
                    bank_acc = BankAccount.search([
                        ('employee_id', '=', self.id),
                        ('account_number', '=', acc_no)
                    ], limit=1)
                    if not bank_acc:
                        # Create automatically if it doesn't exist
                        bank_acc = BankAccount.create({
                            'employee_id': self.id,
                            'account_number': acc_no,
                            'account_type': loan_type.bank_account_type or 'loan_settlement',
                        })
                        _logger.info("LOAN_SYNC: Created new Bank Account '%s' for %s", acc_no, self.name)

                # 4. Find or Create Loan record
                loan_rec = Loan.search([('external_ref', '=', ref)], limit=1)
                
                vals = {
                    'employee_id': self.id,
                    'loan_type_id': loan_type.id,
                    'principal_amount': requested,
                    'monthly_installment': installment,
                    'api_remaining_amount': remaining,
                    'api_status': status,
                    'api_account_number': acc_no,
                    'external_ref': ref,
                    'is_external': True,
                    'bank_account_id': bank_acc.id if bank_acc else False,
                    # Set installment_months as a placeholder since it's required
                    'installment_months': int(requested / installment) if installment > 0 else 1,
                    'date_start': fields.Date.today(),
                }

                # Status Mapping
                # "we let us always check if the status is 'A' or active and if it 'C' or any other letter other than 'A' don't deduct"
                if status == 'A':
                    vals['state'] = 'approved'
                else:
                    vals['state'] = 'completed' # Completed loans are not deducted in _get_ahadu_new_loan_deduction
                
                if loan_rec:
                    loan_rec.write(vals)
                else:
                    Loan.create(vals)
                
                synced_count += 1
                
        except Exception as e:
            _logger.exception("LOAN_SYNC: Failed for employee %s (CIF: %s)", self.name, self.cif)
            errors.append(str(e))
            
        return synced_count, errors

    @api.model
    def cron_sync_external_loans(self):
        """Worker for daily loan sync at 4 AM."""
        employees = self.search([('cif', '!=', False)])
        _logger.info("LOAN_SYNC: Starting daily sync for %s employees.", len(employees))
        
        total_synced = 0
        for emp in employees:
            count, errors = emp._sync_external_loans()
            total_synced += count
            if errors:
                _logger.error("LOAN_SYNC: Errors for %s: %s", emp.name, errors)
            
            # Commit periodically
            if total_synced % 20 == 0:
                self.env.cr.commit()
                
        _logger.info("LOAN_SYNC: Finished daily sync. Total loans processed: %s", total_synced)
