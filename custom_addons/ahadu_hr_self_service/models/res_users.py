from odoo import models, api


class ResUsers(models.Model):
    _inherit = "res.users"

    @property
    def WEBSITE_HOME_ACTION(self):
        # Redirects the user to the frontend website root '/'
        return self.env["ir.actions.act_url"].sudo()._get_action_dict("/")
    
    @property
    def SELF_SERVICE_HOME_ACTION(self):
        return self.env["ir.actions.act_url"].sudo()._get_action_dict("/my/dashboard")

    def _get_home_action(self):
        if self.env.user.has_group("base.group_user") and not self.env.user.has_group(
            "base.group_portal"
        ):
            # For internal users, redirect them to the self-service dashboard
            return self.SELF_SERVICE_HOME_ACTION
        return super()._get_home_action()
