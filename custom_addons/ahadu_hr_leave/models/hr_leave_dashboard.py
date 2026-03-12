
import json
from odoo import models, fields, api
from datetime import date
from dateutil.relativedelta import relativedelta

class HrLeaveDashboard(models.Model):
    _name = 'ahadu.hr.leave.dashboard'
    _description = 'Leave Dashboard'

    name = fields.Char(default="Dashboard")
    

    
    @api.model
    def _create_dashboard_record(self):
        """
        This method is called from a data file to ensure that exactly one
        dashboard record exists for the Kanban view to display.
        """
        if not self.search([], limit=1):
            self.create({})

    @api.model
    def get_dashboard_data(self, dashboard_id=None):
        """
        This is the single data source for our entire dashboard.
        It's called by the JavaScript component.
        """
        employee = self.env['hr.employee'].search([('user_id', '=', self.env.user.id)], limit=1)
        
        balance_cards = []
        if employee:
            today = fields.Date.today()
            one_year_ago = today - relativedelta(years=1)

            allocations = self.env['hr.leave.allocation'].search([
                ('employee_id', '=', employee.id),
                ('state', '=', 'validate'),
                '|',
                    ('effective_remaining_leaves', '>', 0),
                '&',
                    ('expiry_date', '>=', one_year_ago),
                    ('expired_leaves', '>', 0)
            ], order='expiry_date asc')

            for alloc in allocations:
                # This logic remains the same
                is_expired = alloc.expiry_date and alloc.expiry_date < today and alloc.effective_remaining_leaves <= 0

                card_data = {
                    'name': alloc.name,
                    'is_expired': is_expired,
                    'expiry_date': alloc.expiry_date.strftime('%Y-%m-%d') if alloc.expiry_date else False,
                }

                if is_expired:
                    card_data['days'] = f"{alloc.expired_leaves:.2f}"
                else:
                    card_data['days'] = f"{alloc.effective_remaining_leaves:.2f}"
                
                balance_cards.append(card_data)

        # Navigation cards remain the same
        nav_cards = [
            {'name': 'My Allocation', 'action_name': 'action_open_my_allocations', 'icon': 'fa-calendar-plus-o'},
            {'name': 'My Leaves', 'action_name': 'action_open_my_time_off', 'icon': 'fa-calendar'},
            # {'name': 'My Leaves', 'action_name': 'action_open_my_leave', 'icon': 'fa-calendar'},
            {'name': 'Overview', 'action_name': 'action_open_overview', 'icon': 'fa-bar-chart'},
            # {'name': 'Calendar', 'action_name': 'action_open_calendar', 'icon': 'fa-calendar-o'},
        ]

        return {
            'balance_cards': balance_cards,
            'nav_cards': nav_cards,
        }


    # --- ACTION METHODS (called by the JS) ---
    def call_action(self, action_name):
        """Helper method to call a specific action by name."""
        self.ensure_one() # We need a record to call the method on
        action_method = getattr(self, action_name, None)
        if action_method:
            return action_method()
        return False

    def action_open_my_allocations(self):
        return self.env['ir.actions.act_window']._for_xml_id('hr_holidays.hr_leave_allocation_action_my')

    # def action_open_my_leave(self):
    #     return self.env['ir.actions.act_window']._for_xml_id('hr_holidays.hr_leave_action_my')

    def action_open_my_time_off(self):
        return self.env['ir.actions.act_window']._for_xml_id('ahadu_hr_leave.action_ahadu_my_time_off_hub')

    def action_open_overview(self):
        return self.env['ir.actions.act_window']._for_xml_id('hr_holidays.action_hr_holidays_dashboard')

    def action_open_calendar(self):
        # return self.env['ir.actions.actions']._for_xml_id('ahadu_hr_leave.ahadu_calendar_view_action_client')
        return self.env['ir.actions.actions']._for_xml_id('hr.leave.view.dashboard')

    @api.model
    def _get_dashboard_action(self):
        # We need to ensure a record exists to call methods on
        dashboard = self.search([], limit=1)
        if not dashboard:
            dashboard = self.create({})

        return {
            'type': 'ir.actions.client',
            'tag': 'ahadu_leave_dashboard_tag',
            # Pass the database ID of our dashboard record to the JS component
            'params': {'dashboard_id': dashboard.id},
        }