# from odoo import http


# class AhaduTheme(http.Controller):
#     @http.route('/ahadu_theme/ahadu_theme', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/ahadu_theme/ahadu_theme/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('ahadu_theme.listing', {
#             'root': '/ahadu_theme/ahadu_theme',
#             'objects': http.request.env['ahadu_theme.ahadu_theme'].search([]),
#         })

#     @http.route('/ahadu_theme/ahadu_theme/objects/<model("ahadu_theme.ahadu_theme"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('ahadu_theme.object', {
#             'object': obj
#         })

