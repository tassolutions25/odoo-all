import hashlib
import odoo
from odoo import http
from odoo.tools import pycompat
from odoo.tools.translate import _
from odoo.http import request
from odoo.addons.web.controllers.home import Home as WebHome
from odoo.addons.web.controllers.utils import ensure_db, _get_login_redirect_url,is_user_internal

SIGN_UP_REQUEST_PARAMS = {'db', 'login', 'debug', 'token', 'message', 'error', 'scope', 'mode',
                          'redirect', 'redirect_hostname', 'email', 'name', 'partner_id',
                          'password', 'confirm_password', 'city', 'country_id', 'lang', 'signup_email'}
LOGIN_SUCCESSFUL_PARAMS = set()

CREDENTIAL_PARAMS = ['login', 'password', 'type']
def _login_redirect(self, uid, redirect=None):
    return _get_login_redirect_url(uid, redirect)


class Home(WebHome):
    @http.route(route='/web/login', type='http', auth="none")
    def web_login(self, redirect=None, **kw):
        """
        Override web_login to apply a custom theme, while preserving all core
        Odoo login and signup functionality.
        """
        
        response = super(Home, self).web_login(redirect=redirect, **kw)

       
        if response.status_code in (301, 302, 303):
            return response

        values = response.qcontext

        conf_param = request.env['ir.config_parameter'].sudo()
        orientation = conf_param.get_param('ahadu_theme.orientation')
        image = conf_param.get_param('ahadu_theme.image')
        url = conf_param.get_param('ahadu_theme.url')
        background_type = conf_param.get_param('ahadu_theme.background')
        if background_type == 'color':
            values['bg'] = ''
            values['color'] = conf_param.sudo().get_param('ahadu_theme.color')
        elif background_type == 'image' and image:
            exist_rec = request.env['ir.attachment'].sudo().search([('is_background', '=', True)])
            if exist_rec:
                exist_rec.unlink()
            attachments = request.env['ir.attachment'].sudo().create({
                'name': 'Background Image', 'datas': image, 'type': 'binary',
                'mimetype': 'image/png', 'public': True, 'is_background': True
            })
            base_url = conf_param.sudo().get_param('web.base.url') or request.httprequest.url_root
            url = base_url.rstrip('/') + '/web/image?' + 'model=ir.attachment&id=' + str(attachments.id) + '&field=datas'
            values['bg_img'] = url or ''
        elif background_type == 'url' and url:
            pre_exist = request.env['ir.attachment'].sudo().search([('url', '=', url)])
            if not pre_exist:
                attachments = request.env['ir.attachment'].sudo().create({
                    'name': 'Background Image URL', 'url': url, 'type': 'url', 'public': True
                })
            else:
                attachments = pre_exist
            encode = hashlib.md5(pycompat.to_text(attachments.url).encode("utf-8")).hexdigest()[0:7]
            encode_url = "/web/image/{}-{}".format(attachments.id, encode)
            values['bg_img'] = encode_url or ''
            
        if orientation == 'right':
            return request.render('ahadu_theme.login_template_right', values)
        elif orientation == 'left':
            return request.render('ahadu_theme.login_template_left', values)
        elif orientation == 'middle':
            return request.render('ahadu_theme.login_template_middle', values)
        
        
        return response

    @http.route('/web/login_successful', type='http', auth='user', website=True, sitemap=False)
    def login_successful_external_user(self, **kwargs):
        """This function remains unchanged."""
        valid_values = {k: v for k, v in kwargs.items() if k in LOGIN_SUCCESSFUL_PARAMS}
        return request.render('web.login_successful', valid_values)
