# -*- coding: utf-8 -*-
import io
import os
import logging
import uuid
from odoo import http, fields
from odoo.http import request
from odoo.exceptions import UserError
from odoo.tools.misc import xlsxwriter
from collections import defaultdict
from .common import AhaduReportCommon

_logger = logging.getLogger(__name__)

class CashIndemnityReport(AhaduReportCommon):
    
    @http.route('/ahadu_payroll/cash_indemnity_report/<int:batch_id>', type='http', auth='user')
    def download_cash_indemnity_report(self, batch_id, **kw):
        batch = request.env['hr.payslip.run'].browse(batch_id)
        if batch.state not in ['verify', 'close']:
            raise UserError(_("The Cash Indemnity report can only be generated for 'To Verify' or 'Done' payroll batches."))
            
        # Removed: This restriction is now handled by the actual Bank Transfer action
        # if batch.cash_indemnity_done:
        #     raise UserError(_("Cash Indemnity Bank Transfer has already been processed for this batch. You cannot pay twice."))

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        
        # --- SHEET 1: CALCULATION TABLE ---
        worksheet1 = workbook.add_worksheet('Cash Indemnity Sheet')
        
        # Formats
        title_fmt = workbook.add_format({'bold': True, 'size': 12, 'align': 'center', 'bg_color': '#D3D3D3', 'border': 1})
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#f2f2f2', 'border': 1, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True, 'font_size': 9})
        border_fmt = workbook.add_format({'border': 1, 'font_size': 9})
        money_fmt = workbook.add_format({'num_format': '#,##0.00', 'border': 1, 'font_size': 9})
        total_fmt = workbook.add_format({'bold': True, 'bg_color': '#f2f2f2', 'border': 1, 'num_format': '#,##0.00'})
        
        # Title
        worksheet1.merge_range('A1:J1', 'PAYMENT OF CASH INDEMNITY ALLOWANCE FOR CLERICAL STAFFS', title_fmt)
        date_range = f"From {batch.date_start} up to {batch.date_end}" if batch.date_start else ""
        worksheet1.merge_range('A2:J2', date_range, workbook.add_format({'align': 'center', 'bold': True}))
        
        # Headers
        headers = [
            'S.N', 'Name of Employee', 
            'Cash Indemnity Allowance', 'Gross Cash Indemnity Allowance', 
            'Taxable Cash Indemnity Allowance', 'Income Tax', 
            'Net Cash Indemnity Allowance Cr Block Account', 
            'Net Cash Indemnity Allowance Cr Salary Account', 
            'Cash Indemnity Account', 'Saving Account'
        ]
        
        row = 3
        for col, h in enumerate(headers):
            worksheet1.write(row, col, h, header_fmt)
            width = 30 if col == 1 else 15
            if col in [8, 9]: width = 20
            worksheet1.set_column(col, col, width)
            
        row += 1
        seq = 1
        totals = {k: 0.0 for k in ['allowance', 'gross', 'taxable', 'tax', 'net_block', 'net_salary']}
        
        # Helper to find accounts
        def get_acc(partner, type_code):
             return self._get_bank_account(partner, type_code) or ''

        for slip in self._get_payslip_lines(batch):
            if slip.cash_indemnity_allowance > 0 or slip.net_cash_indemnity > 0:
                
                allowance = slip.cash_indemnity_allowance
                tax = slip.cash_indemnity_tax
                net_block = slip.ci_to_balance
                net_salary = slip.ci_to_salary
                
                # Accounts
                ci_acc_num = get_acc(slip.employee_id, 'cash_indemnity')
                sal_acc_num = get_acc(slip.employee_id, 'salary')
                
                worksheet1.write(row, 0, seq, border_fmt)
                worksheet1.write(row, 1, slip.employee_id.name, border_fmt)
                worksheet1.write(row, 2, allowance, money_fmt)
                worksheet1.write(row, 3, allowance, money_fmt) # Gross same as allowance
                worksheet1.write(row, 4, allowance, money_fmt) # Taxable same as allowance
                worksheet1.write(row, 5, tax, money_fmt)
                worksheet1.write(row, 6, net_block, money_fmt)
                worksheet1.write(row, 7, net_salary, money_fmt)
                worksheet1.write(row, 8, ci_acc_num, border_fmt)
                worksheet1.write(row, 9, sal_acc_num, border_fmt)
                
                totals['allowance'] += allowance
                totals['gross'] += allowance
                totals['taxable'] += allowance
                totals['tax'] += tax
                totals['net_block'] += net_block
                totals['net_salary'] += net_salary
                
                row += 1
                seq += 1
        
        # Totals Row
        worksheet1.merge_range(row, 0, row, 1, 'Total', workbook.add_format({'bold': True, 'border': 1, 'align': 'right', 'color': 'red'}))
        worksheet1.write(row, 2, totals['allowance'], total_fmt)
        worksheet1.write(row, 3, totals['gross'], total_fmt)
        worksheet1.write(row, 4, totals['taxable'], total_fmt)
        worksheet1.write(row, 5, totals['tax'], total_fmt)
        worksheet1.write(row, 6, totals['net_block'], total_fmt)
        worksheet1.write(row, 7, totals['net_salary'], total_fmt)
        worksheet1.write(row, 8, '', border_fmt)
        worksheet1.write(row, 9, '', border_fmt)

        # Footer
        row += 3
        worksheet1.write(row, 0, "Prepared By: _________________", workbook.add_format({'font_size': 10}))
        worksheet1.write(row, 4, "Checked By: _________________", workbook.add_format({'font_size': 10}))
        worksheet1.write(row, 8, "Approved By: _________________", workbook.add_format({'font_size': 10}))


        # --- SHEET 2: PAYMENT TICKETS ---
        worksheet2 = workbook.add_worksheet('Payment Tickets')
        
        # Styles for Tickets
        font_name = 'Times New Roman'
        
        style_header = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_size': 12, 'font_name': font_name})
        style_label = workbook.add_format({'bold': True, 'font_size': 11, 'border': 1, 'bg_color': '#bfbfbf', 'align': 'center', 'valign': 'vcenter', 'font_name': font_name}) 
        style_data = workbook.add_format({'border': 1, 'font_size': 11, 'align': 'center', 'valign': 'vcenter', 'font_name': font_name, 'bg_color': '#bfbfbf'})
        style_data_box = workbook.add_format({'border': 1, 'font_size': 11, 'align': 'center', 'valign': 'vcenter', 'font_name': font_name, 'bg_color': '#bfbfbf'})

        style_red_label = workbook.add_format({'font_color': 'red', 'bold': True, 'font_size': 10, 'align': 'left', 'font_name': font_name})
        style_blue_label = workbook.add_format({'font_color': 'blue', 'bold': True, 'font_size': 10, 'align': 'left', 'font_name': font_name})
        
        style_bold = workbook.add_format({'bold': True, 'font_name': font_name, 'font_size': 10})
        style_underline = workbook.add_format({'bottom': 1, 'align': 'left', 'font_name': font_name, 'font_size': 11, 'bold': True})
        style_normal = workbook.add_format({'font_name': font_name, 'font_size': 10})
        style_money = workbook.add_format({'font_name': font_name, 'font_size': 11, 'num_format': '#,##0.00', 'align': 'right', 'bold': True})
        style_money_box = workbook.add_format({'border': 1, 'font_name': font_name, 'font_size': 11, 'num_format': '#,##0.00', 'align': 'center', 'bold': True})

        
        # Set Columns
        worksheet2.set_column(0, 0, 25)
        worksheet2.set_column(1, 1, 25)
        worksheet2.set_column(2, 2, 2)  # GAP
        worksheet2.set_column(3, 3, 25)
        worksheet2.set_column(4, 4, 25)
        
        # Logo Path
        image_path = False
        try:
             # Just use raw string path if needed or get module resource if standard
             from odoo.modules.module import get_module_resource
             image_path = get_module_resource('ahadu_payroll', 'src', 'images', 'Ahadu Bank Logo with Name.jpg')
        except: pass
        
        # Accounts
        acc_allowance = '5030201' # Debit
        acc_tax = '2020301'       # Credit
        
        row = 0
        
        # Re-defining write_ticket wrapper to handle right value cleanly
        def draw_ticket(curr_row, title, is_debit, left_header, left_value, right_header, right_value, amount, slip):
            # Dynamic Fields
            cost_center = '999914'
            if slip.contract_id and hasattr(slip.contract_id, 'cost_center_id') and slip.contract_id.cost_center_id:
                cc = slip.contract_id.cost_center_id
                cost_center = getattr(cc, 'name', '') or getattr(cc, 'code', '') or '999914'
            
            branch_name = 'Head office'
            emp = slip.employee_id
            if hasattr(emp, 'branch_id') and emp.branch_id:
                branch_name = emp.branch_id.name
            elif hasattr(emp, 'branh_id') and emp.branh_id: # Handle typo just in case
                branch_name = emp.branh_id

            # Logo
            try:
                if image_path and os.path.exists(image_path):
                    worksheet2.insert_image(curr_row, 2, image_path, {'x_scale': 0.6, 'y_scale': 0.6, 'x_offset': -25})
            except Exception: pass
            
            # Header
            worksheet2.merge_range(curr_row+1, 0, curr_row+1, 4, branch_name, workbook.add_format({'align': 'center', 'bold': True, 'font_color': '#003366', 'font_name': font_name}))
            worksheet2.merge_range(curr_row+2, 0, curr_row+2, 4, title, workbook.add_format({'align': 'center', 'bold': True, 'font_color': '#003366', 'font_name': font_name, 'font_size': 11}))
            
            # Date
            date_str = fields.Date.today().strftime('%d-%b-%y')
            worksheet2.write(curr_row+2, 3, "Date", workbook.add_format({'bold': True, 'align': 'right', 'font_name': font_name}))
            worksheet2.write(curr_row+2, 4, date_str, workbook.add_format({'align': 'center', 'font_name': font_name})) 

            # Labels
            if is_debit:
                worksheet2.write(curr_row+3, 0, f"cost center {cost_center}", style_bold)
                worksheet2.write(curr_row+4, 0, "Debit", style_underline)
                worksheet2.write(curr_row+4, 2, "Contra", style_red_label)
            else:
                worksheet2.write(curr_row+4, 0, "Contra", style_underline)
                worksheet2.write(curr_row+4, 2, "Credit", style_red_label)
                
            # Boxes
            worksheet2.merge_range(curr_row+5, 0, curr_row+5, 1, left_header, style_label)
            worksheet2.merge_range(curr_row+6, 0, curr_row+6, 1, left_value, style_data_box)
            
            worksheet2.merge_range(curr_row+5, 3, curr_row+5, 4, right_header, style_label)
            worksheet2.merge_range(curr_row+6, 3, curr_row+6, 4, right_value, style_data_box)  
            
            # Narrative
            period = f"{batch.date_start.strftime('%B,%d %Y')} Upto {batch.date_end.strftime('%B %d,%Y')}" if batch.date_start else ""
            desc_text = "cash indemnity allowance" if "cash" in left_header.lower() else left_header
            narrative = f"{desc_text} payment to {slip.employee_id.name} for the month of {period}."
            worksheet2.merge_range(curr_row+7, 0, curr_row+8, 4, narrative, workbook.add_format({'text_wrap': True, 'valign': 'top', 'font_name': font_name}))
            
            # Amount
            worksheet2.write(curr_row+9, 0, "Birr", style_bold)
            amount_text = slip.company_id.currency_id.amount_to_text(amount) if slip.company_id.currency_id else str(amount)
            worksheet2.merge_range(curr_row+10, 0, curr_row+10, 2, amount_text, workbook.add_format({'bottom': 1, 'text_wrap': True, 'font_name': font_name, 'font_size': 9}))
            
            worksheet2.write(curr_row+10, 3, "Birr", workbook.add_format({'bold': True, 'align': 'right', 'font_name': font_name}))
            worksheet2.write(curr_row+10, 4, amount, style_money)
            
            # Signature
            worksheet2.merge_range(curr_row+12, 0, curr_row+12, 1, "Prepared By", workbook.add_format({'top': 1, 'bold': True, 'align': 'center', 'font_name': font_name}))
            worksheet2.write(curr_row+12, 2, "Checked By", workbook.add_format({'top': 1, 'bold': True, 'align': 'center', 'font_name': font_name}))
            worksheet2.merge_range(curr_row+12, 3, curr_row+12, 4, "Approved by", workbook.add_format({'top': 1, 'bold': True, 'align': 'center', 'font_name': font_name}))
            
            return curr_row + 14

        for slip in self._get_payslip_lines(batch):
             if slip.cash_indemnity_allowance > 0:
                emp_name = slip.employee_id.name
                allowance = slip.cash_indemnity_allowance
                tax = slip.cash_indemnity_tax
                net_ci = slip.ci_to_balance
                net_sal = slip.ci_to_salary

                ci_acc_num = get_acc(slip.employee_id, 'cash_indemnity')
                sal_acc_num = get_acc(slip.employee_id, 'salary')
                
                # Ticket 1: Debit Ticket
                row = draw_ticket(row, "Debit Ticket", True, 
                    "cash indemnity allowance", acc_allowance, 
                    emp_name, f"{ci_acc_num}/{sal_acc_num or 'N/A'}", 
                    allowance, slip)
                
                # Ticket 2: Credit Ticket (Tax)
                row = draw_ticket(row, "Credit Ticket", False, 
                    "cash indemnity allowance", acc_allowance, 
                    "income tax payable", acc_tax, 
                    tax, slip)

                # Ticket 3: Credit Ticket (Net CI)
                if net_ci > 0:
                     row = draw_ticket(row, "Credit Ticket", False, 
                        "cash indemnity allowance", acc_allowance, 
                        emp_name, ci_acc_num, 
                        net_ci, slip)
                
                # Ticket 4: Credit Ticket (Net Salary)
                if net_sal > 0:
                     row = draw_ticket(row, "Credit Ticket", False, 
                        "cash indemnity allowance", acc_allowance, 
                        emp_name, sal_acc_num, 
                        net_sal, slip)
                
                row += 1 # Spacer

        # --- SHEET 3: BANK TRANSFER (CASH INDEMNITY) ---
        worksheet3 = workbook.add_worksheet('Bank Transfer')
        
        # Styles
        style_text_s3 = workbook.add_format({'font_name': 'Times New Roman', 'font_size': 11})
        style_money_s3 = workbook.add_format({'font_name': 'Times New Roman', 'font_size': 11, 'num_format': '#,##0.00'})
        
        worksheet3.set_column(0, 0, 20)
        worksheet3.set_column(1, 1, 5)
        worksheet3.set_column(2, 2, 15)
        worksheet3.set_column(3, 3, 30) # LOG column
        
        # Aggregation: { account: { 'amount': sum, 'emp': [names] } }
        from collections import defaultdict
        ci_aggregated = defaultdict(lambda: {'amount': 0.0, 'emp': []})
        ci_total_credit = 0.0
        
        for slip in self._get_payslip_lines(batch):
            if slip.ci_to_balance > 0:
                acc = get_acc(slip.employee_id, 'cash_indemnity') or 'N/A'
                ci_aggregated[acc]['amount'] += slip.ci_to_balance
                if slip.employee_id.name not in ci_aggregated[acc]['emp']:
                    ci_aggregated[acc]['emp'].append(slip.employee_id.name)
                ci_total_credit += slip.ci_to_balance

            if slip.ci_to_salary > 0:
                acc = get_acc(slip.employee_id, 'salary') or 'N/A'
                ci_aggregated[acc]['amount'] += slip.ci_to_salary
                if slip.employee_id.name not in ci_aggregated[acc]['emp']:
                    ci_aggregated[acc]['emp'].append(slip.employee_id.name)
                ci_total_credit += slip.ci_to_salary

        row_s3 = 0
        funding_acc = '9999-1040309' 
        worksheet3.write(row_s3, 0, funding_acc, style_text_s3)
        worksheet3.write(row_s3, 1, 'D', style_text_s3)
        worksheet3.write(row_s3, 2, ci_total_credit, style_money_s3)
        worksheet3.write(row_s3, 3, 'Funding Account', style_text_s3)
        row_s3 += 1
        
        for acc, data in ci_aggregated.items():
            # In the Cash Indemnity Report, we no longer call the API.
            # We just list the payments that will be performed by the Bank Transfer button.
            status = "Transfer pending Bank Transfer action"
            
            worksheet3.write(row_s3, 0, acc, style_text_s3)
            worksheet3.write(row_s3, 1, 'C', style_text_s3)
            worksheet3.write(row_s3, 2, data['amount'], style_money_s3)
            worksheet3.write(row_s3, 3, status, style_text_s3) # LOG column
            row_s3 += 1

        # NOTE: We no longer mark the batch as cash_indemnity_done here.
        # This allows the report to be generated multiple times before the actual transfer.

        workbook.close() 
        output.seek(0)
        return self._make_excel_response(output, f'Cash_Indemnity_{batch.name}.xlsx')
