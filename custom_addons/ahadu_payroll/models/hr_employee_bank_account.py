# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import requests
import logging
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class HrEmployeeBankAccount(models.Model):
    _inherit = 'hr.employee.bank.account'
    _rec_name = 'account_number'

    last_sync_date = fields.Datetime(string="Last Sync Date", readonly=True)

    @api.depends('account_number', 'account_type')
    def _compute_display_name(self):
        for acc in self:
            # Resilient fetching of account number
            acc_no = acc.account_number or (acc.acc_number if hasattr(acc, 'acc_number') else '')
            type_label = dict(self._fields['account_type'].selection).get(acc.account_type, acc.account_type) or ''
            acc.display_name = f"{acc_no} ({type_label})" if acc_no else f"Account {acc.id} ({type_label})"

    @api.model
    def _name_search(self, name, domain=None, operator='ilike', limit=None, order=None):
        domain = domain or []
        if name:
            # Broaden search to include both potential account number fields
            search_domain = [('account_number', operator, name)]
            if hasattr(self, 'acc_number'):
                search_domain = ['|'] + search_domain + [('acc_number', operator, name)]
            domain = search_domain + domain
        return self._search(domain, limit=limit, order=order)

    def action_sync_core_balance(self):
        """Fetches the real balance from the core bank system."""
        self.ensure_one()
        url = "http://10.20.1.11:7034/olive/publisher/getAccountDetails"
        headers = {'Content-Type': 'application/json'}
        data = {
            "AccountId": self.account_number
        }
        
        try:
            response = requests.post(url, json=data, headers=headers, timeout=10)
            response.raise_for_status()
            res_data = response.json()
            
            resp_body = res_data.get('Response', {})
            status_code = resp_body.get('StatusCode')
            status_desc = resp_body.get('StatusDescription')
            
            if status_code == "SUCCESS":
                current_balance = resp_body.get('CurrentBalance')
                if current_balance is not None:
                    self.write({
                        'balance': float(current_balance),
                        'last_sync_date': fields.Datetime.now()
                    })
                else:
                    _logger.warning("CurrentBalance is null in successful response for account %s", self.account_number)
            else:
                _logger.error("Failed to fetch balance for account %s: %s", self.account_number, status_desc)
                raise UserError(_("Core Banking API Error: %s") % status_desc)
                
        except requests.exceptions.RequestException as e:
            _logger.error("Connection error while fetching balance for account %s: %s", self.account_number, str(e))
            raise UserError(_("Could not connect to Core Banking System. Please check connectivity."))
        except Exception as e:
            _logger.error("Unexpected error while fetching balance for account %s: %s", self.account_number, str(e))
            raise UserError(_("An unexpected error occurred: %s") % str(e))

    @api.model
    def cron_sync_cash_indemnity_balances(self):
        """Automated sync for all cash indemnity accounts."""
        accounts = self.search([('account_type', '=', 'cash_indemnity')])
        _logger.info("Starting automated balance sync for %s cash indemnity accounts", len(accounts))
        for acc in accounts:
            try:
                acc.action_sync_core_balance()
                # Commit after each sync to ensure partial success is saved
                self.env.cr.commit()
            except Exception as e:
                _logger.error("Cron failed to sync balance for account %s: %s", acc.account_number, str(e))
        _logger.info("Automated balance sync completed")
