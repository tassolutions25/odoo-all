# -*- coding: utf-8 -*-
from odoo import models, fields

class ResourceCalendar(models.Model):
    _inherit = 'resource.calendar'

    # The field for Shift Management
    shift_category = fields.Selection([
        ('day', 'Day Shift'),
        ('night', 'Night Shift'),
        ('branch', 'Branch Shift'),
        ('ho', 'Head Office Shift'),
        ('flexible', 'Flexible')
    ], string="Shift Category", default='day')

    # The field for Lateness Tolerance
    tolerance_late_check_in = fields.Float(
        string="Late Check-in Tolerance (Minutes)", 
        default=15.0, 
        help="Allowed delay in minutes before an employee is marked as late."
    )


# from odoo import models, fields

# class ResourceCalendar(models.Model):
#     # This is the critical fix: inherit from the correct base Odoo model
#     _inherit = 'resource.calendar'

#     tolerance_late_check_in = fields.Float(
#         string="Late Check-in Tolerance (Minutes)", 
#         default=15.0, 
#         help="Allowed delay in minutes before an employee is marked as late."
#     )

#     def _is_rest_day(self, day_dt):
#         """ 
#         Helper method to check if a given date is a rest day.
#         Note: Odoo has a similar built-in method _is_work_day which also considers global leaves.
#         """
#         self.ensure_one()
#         # The weekday() method returns Monday as 0 and Sunday as 6.
#         # The 'dayofweek' field in Odoo is a string '0' for Monday, '1' for Tuesday, etc.
#         day_of_week_str = str(day_dt.weekday())
        
#         # Find if there are any working intervals defined for that day of the week.
#         attendance_rules = self.attendance_ids.filtered(
#             lambda att: att.dayofweek == day_of_week_str and att.display_type is False
#         )
        
#         # If there are no rules, it's a rest day.
#         return not attendance_rules

