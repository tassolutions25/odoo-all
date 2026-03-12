# -*- coding: utf-8 -*-
import logging
import requests
import urllib.parse
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
