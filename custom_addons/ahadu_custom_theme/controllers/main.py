from odoo import http, SUPERUSER_ID
from odoo.http import request
try:
    from odoo.addons.ahadu_theme.controllers.main import Home as AhaduHome
except ImportError:
    # If ahadu_theme is not present, define a dummy class or just use WebHome
    # But manifest says it depends on it, so it should be there.
    # We'll rely on correct environment.
    from odoo.addons.web.controllers.home import Home as AhaduHome

from odoo.addons.auth_signup.controllers.main import AuthSignupHome
from odoo.http import request

import logging
_logger = logging.getLogger(__name__)

class LoginController(AhaduHome, AuthSignupHome):
    
    @http.route(route='/web/login', type='http', auth="none")
    def web_login(self, redirect=None, **kw):
        # Intercept POST request to swap Employee ID with User Login
        if request.httprequest.method == 'POST' and kw.get('login') and kw.get('password'):
            login_input = kw['login']
            # Search for employee by employee_id (case-insensitive)
            employee = request.env['hr.employee'].with_user(SUPERUSER_ID).search([('employee_id', '=ilike', login_input)], limit=1)
            
            if employee:
                if employee.user_id:
                    _logger.info(f"Login attempt: Swapped Employee ID '{login_input}' with User Login '{employee.user_id.login}'")
                    kw['login'] = employee.user_id.login
                    request.params['login'] = employee.user_id.login
                else:
                    _logger.warning(f"Login attempt: Employee ID '{login_input}' found but no related User.")
                    # Fallback to standard flow (will likely fail auth)

        return super(LoginController, self).web_login(redirect=redirect, **kw)

    def get_auth_signup_qcontext(self):
        """
        Override qcontext to swap Employee ID for Email during Reset Password flow.
        This method is called by web_auth_reset_password.
        """
        qcontext = super(LoginController, self).get_auth_signup_qcontext()
        
        if qcontext.get('login'):
            login_input = qcontext['login']
            # Search for employee by employee_id
            employee = request.env['hr.employee'].with_user(SUPERUSER_ID).search([('employee_id', '=ilike', login_input)], limit=1)
            
            if employee and employee.user_id:
                 _logger.info(f"Auth Context: Swapped Employee ID '{login_input}' with User Login '{employee.user_id.login}'")
                 qcontext['login'] = employee.user_id.login
            else:
                # If not an employee ID, assume it's an email/login and keep it as is.
                pass
        
        return qcontext
