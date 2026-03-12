# # models/res_users.py

# from odoo import models, api, _
# from odoo.exceptions import ValidationError


# class ResUsers(models.Model):
#     _inherit = "res.users"

#     @api.constrains("name", "groups_id")
#     def _check_full_name(self):
#         """
#         Strengthened validation:
#         Ensures that any 'Internal User' has a name containing at least
#         a first and last name separated by a space.
#         This does not apply to Portal or Public users.
#         """
#         for user in self:
#             is_internal_user = not user.has_group("base.group_portal")

#             if is_internal_user and user.name and " " not in user.name.strip():
#                 raise ValidationError(
#                     _(
#                         "Internal Users must have a full name containing at least a first and a last name, separated by a space. "
#                         'You entered "%s".',
#                         user.name,
#                     )
#                 )
