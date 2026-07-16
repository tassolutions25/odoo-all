# -*- coding: utf-8 -*-
import logging
import requests
import urllib.parse
from datetime import date, datetime
from odoo import fields
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

class AhaduReportCommon(http.Controller):

    def _make_excel_response(self, output, filename):
        """
        Creates a robust HTTP response for downloading Excel files.
        Ensures the filename is properly quoted and sanitized to prevent 
        issues on remote devices or with strict network proxies.
        """
        # Sanitize filename: remove semicolons, commas, and other problematic chars
        safe_filename = filename.replace(';', '').replace(',', '').replace('"', '').replace("'", "")
        # Quote specifically for Content-Disposition
        quoted_filename = urllib.parse.quote(safe_filename)
        
        headers = [
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', f'attachment; filename*=UTF-8\'\'{quoted_filename}'),
            ('Cache-Control', 'no-cache, no-store, must-revalidate'),
            ('Pragma', 'no-cache'),
            ('Expires', '0'),
        ]
        return request.make_response(output.getvalue(), headers=headers)

    def _get_payslip_lines(self, batch):
        """Helper to get confirmed slips from a batch."""
        return batch.slip_ids.filtered(lambda s: s.state in ['done', 'paid', 'verify'])

    def _get_rule_total(self, slip, codes):
        """Helper to sum rules by code."""
        if isinstance(codes, str):
            codes = [codes]
        total = 0.0
        for line in slip.line_ids:
            if line.code in codes:
                total += line.total
        return total

    def _get_gl_codes(self, codes, side='debit'):
        """Get GL codes for a set of rules. Returns unique codes joined by slash if multiple."""
        # This is a bit specific to how rules are configured, assuming we have access to rule objects via codes?
        # The original code didn't actually use slip lines, it used rules.
        # But wait, the original code in main.py:
        # def _get_gl_codes(self, codes, side='debit'):
        #     rules = request.env['hr.salary.rule'].search([('code', 'in', codes)])
        #     ...
        if isinstance(codes, str):
            codes = [codes]
        rules = request.env['hr.salary.rule'].search([('code', 'in', codes)])
        accounts = []
        for rule in rules:
            acc = rule.ahadu_debit_account_id if side == 'debit' else rule.ahadu_credit_account_id
            if acc and acc.code not in accounts:
                accounts.append(acc.code)
        return " / ".join(accounts)

    def _get_bank_account(self, partner, type_code):
        """Helper to find bank account by type."""
        acc = request.env['hr.employee.bank.account'].sudo().search([
            ('employee_id', '=', partner.id),
            ('account_type', '=', type_code)
        ], limit=1)
        return acc.account_number if acc else ''

    def _write_ticket_claim_sheet(self, workbook, entries, period_label='', branch_name='Head office',
                                  processed_date=None,
                                  contra_name='Other Receivable', contra_account='1040309',
                                  sheet_name='Ticket Claim'):
        """Write aggregate debit/credit tickets using the finance ticket layout."""
        sheet = workbook.add_worksheet(sheet_name)

        font_name = 'Bookman Old Style'
        title_fmt = workbook.add_format({'font_name': font_name, 'font_size': 12, 'bold': True, 'align': 'center'})
        side_fmt = workbook.add_format({'font_name': font_name, 'font_size': 12, 'bold': True, 'bottom': 2})
        contra_fmt = workbook.add_format({'font_name': font_name, 'font_size': 12, 'bold': True, 'font_color': 'red', 'bottom': 1})
        box_label_fmt = workbook.add_format({
            'font_name': font_name, 'font_size': 12, 'bold': True, 'align': 'center',
            'valign': 'vcenter', 'text_wrap': True, 'border': 1, 'bg_color': '#D9D9D9'
        })
        box_value_fmt = workbook.add_format({
            'font_name': font_name, 'font_size': 12, 'align': 'center',
            'valign': 'vcenter', 'text_wrap': True, 'border': 1, 'bg_color': '#D9D9D9'
        })
        narrative_fmt = workbook.add_format({'font_name': font_name, 'font_size': 12, 'align': 'left', 'text_wrap': True})
        amount_words_fmt = workbook.add_format({'font_name': font_name, 'font_size': 11, 'align': 'left', 'text_wrap': True})
        amount_label_fmt = workbook.add_format({'font_name': font_name, 'font_size': 12, 'bold': True, 'align': 'right'})
        amount_fmt = workbook.add_format({'font_name': font_name, 'font_size': 12, 'bold': True, 'num_format': '#,##0.00'})
        sign_line_fmt = workbook.add_format({'font_name': font_name, 'font_size': 12, 'align': 'center'})
        sign_label_fmt = workbook.add_format({'font_name': font_name, 'font_size': 12, 'bold': True, 'align': 'center'})

        widths = [9.14, 13.28, 16.42, 9.14, 13.0, 13.0, 13.28, 22.14, 16.0]
        for col, width in enumerate(widths):
            sheet.set_column(col, col, width)

        currency = request.env.company.currency_id
        if isinstance(processed_date, datetime):
            ticket_date = processed_date.date()
        elif isinstance(processed_date, date):
            ticket_date = processed_date
        elif processed_date:
            ticket_date = fields.Date.to_date(processed_date)
        else:
            ticket_date = fields.Date.today()
        ticket_date_text = ticket_date.strftime('%d-%b-%y')

        def amount_to_words(amount):
            try:
                return currency.amount_to_text(amount) if currency else str(amount)
            except Exception:
                return str(amount)

        def write_ticket(row, ticket_type, left_name, left_account, right_name, right_account, amount, narrative):
            sheet.merge_range(row, 0, row, 5, branch_name, title_fmt)
            sheet.write(row, 7, 'Date', title_fmt)
            sheet.write(row, 8, ticket_date_text, title_fmt)
            sheet.merge_range(row + 1, 3, row + 1, 5, ticket_type, title_fmt)

            if ticket_type == 'Debit Ticket':
                sheet.write(row + 2, 0, 'Debit', side_fmt)
                sheet.write(row + 2, 6, 'contra', contra_fmt)
            else:
                sheet.write(row + 2, 0, 'Contra', side_fmt)
                sheet.write(row + 2, 6, 'Credit', contra_fmt)

            sheet.merge_range(row + 4, 0, row + 4, 3, left_name, box_label_fmt)
            sheet.merge_range(row + 5, 0, row + 5, 3, left_account, box_value_fmt)
            sheet.merge_range(row + 4, 6, row + 4, 8, right_name, box_label_fmt)
            sheet.merge_range(row + 5, 6, row + 5, 8, right_account, box_value_fmt)
            sheet.merge_range(row + 6, 0, row + 8, 8, narrative, narrative_fmt)
            sheet.write(row + 10, 0, 'Birr', narrative_fmt)
            sheet.merge_range(row + 10, 1, row + 10, 8, amount_to_words(amount), amount_words_fmt)
            sheet.write(row + 12, 6, 'Birr', amount_label_fmt)
            sheet.write(row + 12, 7, amount, amount_fmt)
            sheet.merge_range(row + 14, 0, row + 14, 1, '_____________', sign_line_fmt)
            sheet.merge_range(row + 14, 3, row + 14, 4, '________________', sign_line_fmt)
            sheet.merge_range(row + 14, 6, row + 14, 7, '_____________________', sign_line_fmt)
            sheet.merge_range(row + 15, 0, row + 15, 1, 'Prepared By', sign_label_fmt)
            sheet.merge_range(row + 15, 3, row + 15, 4, 'Checked By', sign_label_fmt)
            sheet.merge_range(row + 15, 6, row + 15, 7, 'Approved by', sign_label_fmt)
            return row + 18

        row = 2
        for entry in entries:
            amount = abs(float(entry.get('amount') or 0.0))
            if round(amount, 2) == 0:
                continue

            desc = entry.get('description') or ''
            account = entry.get('account') or ''
            item_period = entry.get('period_label') or period_label
            narrative = entry.get('narrative') or f"{desc} payment to various staffs for the month of {item_period}."
            counter_name = entry.get('counter_name') or contra_name
            counter_account = entry.get('counter_account') or contra_account

            if entry.get('side') == 'credit':
                debit_narrative = entry.get('debit_narrative') or f"{desc} collected from various staffs for the month of {item_period}."
                row = write_ticket(row, 'Debit Ticket', counter_name, counter_account, desc, account, amount, debit_narrative)
                row = write_ticket(row, 'Credit Ticket', counter_name, counter_account, desc, account, amount, debit_narrative)
            else:
                row = write_ticket(row, 'Debit Ticket', desc, account, counter_name, counter_account, amount, narrative)

    def _call_payroll_api(self, request_id, amount, creditor_acc, gl_acc):
        """
        Calls the external payroll payment API.
        """
        url = 'https://10.20.1.22:8243/erppayrollPayment/1.0.0/payrollPayment'
        headers = {'Content-Type': 'application/json'}
        data = {
            "RequestId": str(request_id),
            "TransactionAmount": str(amount),
            "CreditorAccount": str(creditor_acc),
            "GLAccount": str(gl_acc)
        }
        try:
            # Note: verify=False is used because it's an internal IP with likely self-signed cert
            response = requests.post(url, headers=headers, json=data, timeout=10, verify=False)
            if response.status_code == 200:
                return "Success"
            else:
                return f"Error: {response.status_code} - {response.text}"
        except Exception as e:
            _logger.error(f"Payroll API Connection Failed: {str(e)}")
            return f"Connection Failed: {str(e)}"
