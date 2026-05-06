# -*- coding: utf-8 -*-
import io
import requests
import json
import logging
import zipfile
import uuid
import urllib.parse
from collections import defaultdict
from odoo import http, fields
from odoo.http import request
from odoo.tools.misc import xlsxwriter
from odoo.exceptions import UserError
from .common import AhaduReportCommon

_logger = logging.getLogger(__name__)

class TerminationBankTransferReport(AhaduReportCommon):
    
    def _is_addis_branch(self, branch):
        """Helper to check if a branch is in Addis Ababa."""
        if not branch or not branch.region_id:
            return False
        return 'addis' in (branch.region_id.name or '').lower()

    @http.route('/ahadu_payroll/termination_ping', type='http', auth='user')
    def termination_ping(self, **kw):
        return "Termination Controller is Reachable"

    @http.route('/ahadu_payroll/termination_bank_transfer/<int:batch_id>', type='http', auth='user')
    def download_termination_bank_transfer(self, batch_id, **kw):
        _logger.info("=== DEBUG: download_termination_bank_transfer called with id %s ===", batch_id)
        batch = request.env['hr.termination.run'].browse(batch_id)
        
        if not batch.exists() or batch.state not in ['calculated', 'done']:
            _logger.warning("=== DEBUG: Batch %s not in valid state (%s) ===", batch_id, batch.state if batch.exists() else 'N/A')
            raise UserError("You cannot generate the Bank Transfer File until the termination batch is Verified or Closed.")

        if batch.bank_transfer_done:
            _logger.warning("=== DEBUG: Batch %s already has bank_transfer_done=True ===", batch_id)
            raise UserError("The Bank Transfer has already been processed for this batch. You cannot pay twice.")

        # Aggregate Upload Data: {(account, dc, dept_cc, reason, branch_cc): amount}
        aggregated_upload = defaultdict(float)
        # file3_payments: {(account, funding_gl): {'amount': sum, 'emp': []}}
        file3_payments = defaultdict(lambda: {'amount': 0.0, 'emp': []})
        
        slips = batch.slip_ids.filtered(lambda s: s.state != 'cancel')
        _logger.info("=== DEBUG: Found %s slips for batch %s ===", len(slips), batch.name)
        month_year = batch.date_start.strftime('%b %Y') if batch.date_start else ''
        
        if not slips:
            _logger.warning(f"Termination Bank Transfer: No valid slips found for batch {batch.name}")

        for slip in slips:
            emp = slip.employee_id
            if not emp:
                _logger.warning(f"Termination Bank Transfer: Slip {slip.id} has no employee.")
                continue

            emp_type = emp.ahadu_employee_type_id.code or 'N/A'
            emp_type_name = 'clerical staff' if emp_type == 'CL_STAFF' else 'non clerical staff'
            
            branch = emp.branch_id
            branch_code = branch.cost_center_id.code or '0000' if branch and hasattr(branch, 'cost_center_id') else '0000'
            is_ho = (branch and branch.name == 'Head Office') or branch_code == '9999'
            is_addis = self._is_addis_branch(branch)
            
            branch_prefix = '9999' if is_ho else branch_code
            
            contract = emp.contract_id
            dept_cc = contract.cost_center_id.code or branch_prefix if contract and hasattr(contract, 'cost_center_id') and contract.cost_center_id else branch_prefix
            branch_cc = branch_prefix

            # Funding GLs
            FUNDING_GL_SALARY = '5030101' if emp_type == 'CL_STAFF' else '5030102'

            # 1. Earnings (DEBIT SIDE)
            earnings_map = [
                (slip.unpaid_salary or 0.0, FUNDING_GL_SALARY, f"{emp_type_name} unpaid salary {month_year}"),
                (slip.leave_pay_gross or 0.0, '5030220', f"{emp_type_name} leave pay {month_year}"),
                (slip.unpaid_transport or 0.0, '5030204', f"{emp_type_name} unpaid transport {month_year}"),
                (slip.unpaid_housing or 0.0, '5030205', f"{emp_type_name} unpaid housing {month_year}"),
                (slip.unpaid_mobile or 0.0, '5030221', f"{emp_type_name} unpaid mobile {month_year}"),
                (slip.representation_allowance or 0.0, '5030206', f"{emp_type_name} representation allowance {month_year}"),
                (slip.pension_comp or 0.0, '5030211', f"{emp_type_name} pension comp {month_year}"),
            ]

            for amt, gl, reason in earnings_map:
                if amt > 0:
                    aggregated_upload[(f"{branch_prefix}-{gl}", 'D', dept_cc, reason, branch_cc)] += round(amt, 2)

            # 2. Statutory Deductions (CREDIT SIDE)
            pension_total = (slip.pension_emp or 0.0) + (slip.pension_comp or 0.0)
            statutory_map = [
                (slip.grand_tax or 0.0, '2020301', 'income tax'),
                (pension_total, '2020308', 'pension pay staff 18 per'),
            ]

            for amt, gl, reason_base in statutory_map:
                if amt > 0:
                    crediting_branch = branch_prefix
                    if not is_ho and is_addis:
                        crediting_branch = '9999'
                    
                    reason = f"{reason_base} termination {'ho staffs' if crediting_branch == '9999' else ''} {month_year}"
                    aggregated_upload[(f"{crediting_branch}-{gl}", 'C', '', reason, branch_cc if crediting_branch != '9999' else '')] += round(amt, 2)

            # 3. Penalties & Other Deductions (CREDIT SIDE)
            penalty_amt = (slip.lost_id_card or 0.0) + (slip.vat_on_id_card or 0.0) + (slip.other_deductions or 0.0)
            if penalty_amt > 0:
                gl = '4050012'
                reason = f"termination deductions {month_year}"
                aggregated_upload[(f"{branch_prefix}-{gl}", 'C', '', reason, branch_cc)] += round(penalty_amt, 2)

            # 4. Net Payable (Bank Transfer)
            net = slip.net_payable or 0.0
            _logger.info("=== DEBUG: Employee %s, Net: %s ===", emp.name, net)
            if net > 0:
                acc = self._get_bank_account(emp, 'salary') or 'N/A'
                _logger.info("=== DEBUG: Employee %s, Account: %s ===", emp.name, acc)
                file3_payments[(acc, FUNDING_GL_SALARY)]['amount'] += round(net, 2)
                if emp.name not in file3_payments[(acc, FUNDING_GL_SALARY)]['emp']:
                    file3_payments[(acc, FUNDING_GL_SALARY)]['emp'].append(emp.name)
                aggregated_upload[(acc, 'C', '', f'net termination payment {month_year}', branch_cc)] += round(net, 2)

        _logger.info(f"Termination Bank Transfer: Processed {len(slips)} slips. Entries in upload: {len(aggregated_upload)}")

        # --- Generate Excels ---
        zip_buffer = io.BytesIO()
        try:
            with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
                def get_workbook():
                    out = io.BytesIO()
                    wb = xlsxwriter.Workbook(out, {'in_memory': True})
                    st_text = wb.add_format({'font_name': 'Times New Roman', 'font_size': 11})
                    st_money = wb.add_format({'font_name': 'Times New Roman', 'font_size': 11, 'num_format': '#,##0.00'})
                    return out, wb, st_text, st_money

                safe_batch_name = (batch.name or 'Termination_Batch').replace('/', '_').replace('\\', '_').replace(':', '_')

                # FILE 1: Finance Upload
                f_out, f_wb, f_st, f_curr = get_workbook()
                f_ws = f_wb.add_worksheet('Finance Upload')
                row = 0
                sorted_keys = sorted(aggregated_upload.keys(), key=lambda x: (x[1] == 'C', x[0]))
                for key in sorted_keys:
                    amt = aggregated_upload[key]
                    f_ws.write(row, 0, key[0], f_st)
                    f_ws.write(row, 1, key[1], f_st)
                    f_ws.write(row, 2, amt, f_curr)
                    f_ws.write(row, 3, key[2], f_st)
                    f_ws.write(row, 4, key[3], f_st)
                    f_ws.write(row, 5, key[4], f_st)
                    row += 1
                f_wb.close()
                zip_file.writestr(f"1_Finance_Upload_Termination_{safe_batch_name}.xlsx", f_out.getvalue())

                # FILE 2: Bank Transfer Details
                f3_out, f3_wb, f3_st, f3_curr = get_workbook()
                f3_ws = f3_wb.add_worksheet('Bank Transfer Details')
                row = 0
                for (acc, funding_gl), data in file3_payments.items():
                    raw_id = f"TERM-{batch.name}-{acc}-{funding_gl}"
                    request_id = f"PAY-{uuid.uuid3(uuid.NAMESPACE_DNS, raw_id).hex[:10].upper()}"
                    status = self._call_payroll_api(request_id, data['amount'], acc, funding_gl)
                    
                    f3_ws.write(row, 0, acc, f3_st)
                    f3_ws.write(row, 1, 'C', f3_st)
                    f3_ws.write(row, 2, data['amount'], f3_curr)
                    desc = f"{', '.join(data['emp'][:3])}{'...' if len(data['emp']) > 3 else ''} {batch.name} Term"
                    f3_ws.write(row, 3, desc, f3_st)
                    f3_ws.write(row, 4, status, f3_st)
                    row += 1
                f3_wb.close()
                zip_file.writestr(f"2_Bank_Transfer_Details_Termination_{safe_batch_name}.xlsx", f3_out.getvalue())

            batch.sudo().write({'bank_transfer_done': True})
            _logger.info(f"Termination Bank Transfer: ZIP file generated successfully for batch {batch.name}")
            
        except Exception as e:
            _logger.error(f"Termination Bank Transfer Generation Failed: {str(e)}")
            raise UserError(f"Generation failed: {str(e)}")

        zip_buffer.seek(0)
        zip_filename = f"Termination_Bank_Transfer_{safe_batch_name}.zip"
        quoted_filename = urllib.parse.quote(zip_filename)
        headers = [
            ('Content-Type', 'application/zip'),
            ('Content-Disposition', f'attachment; filename*=UTF-8\'\'{quoted_filename}'),
            ('Cache-Control', 'no-cache, no-store, must-revalidate'),
        ]
        return request.make_response(zip_buffer.getvalue(), headers=headers)
