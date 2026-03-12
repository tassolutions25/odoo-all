# from odoo import models, fields, api, _
# from odoo.exceptions import ValidationError
# from dateutil.relativedelta import relativedelta

# class HrLeave(models.Model):
#     _inherit = 'hr.leave' 

#     is_half_day = fields.Boolean(string="Half Day Request")

#     medical_certificate = fields.Binary(
#         string="Medical Certificate",
#         attachment=True,
#         copy=False,
#         help="Upload the medical certificate or other supporting documents here."
#     )
#     medical_certificate_filename = fields.Char(string="Certificate Filename", copy=False)

#     def _check_medical_certificate(self):
#         """
#         A helper method to check for the presence of a medical certificate
#         for any of the tiered sick leave types.
#         """
#         # Get references to all the actual sick leave types (not the request proxy)
#         sick_leave_types = self.env['hr.leave.type'].search([
#             ('id', 'in', [
#                 self.env.ref('ahadu_hr_leave.ahadu_sick_leave_100_pay').id,
#                 self.env.ref('ahadu_hr_leave.ahadu_sick_leave_50_pay').id,
#                 self.env.ref('ahadu_hr_leave.ahadu_sick_leave_0_pay').id,
#             ])
#         ])
#         sick_leave_type_ids = sick_leave_types.ids

#         for leave in self:
#             if leave.holiday_status_id.id in sick_leave_type_ids and not leave.medical_certificate:
#                 raise ValidationError(_(
#                     "A medical certificate is required to approve this sick leave request. "
#                     "Please ask the employee to edit the request and upload the document."
#                 ))

#     def action_approve(self, *args, **kwargs):
#         """
#         Override the first approval action to enforce the certificate upload.
#         """
#         self._check_medical_certificate()
#         return super(HrLeave, self).action_approve(*args, **kwargs)

#     def action_validate(self):
#         """
#         Override the final validation action (by HR) to also enforce the upload.
#         """
#         self._check_medical_certificate()
#         return super(HrLeave, self).action_validate()

#     @api.model_create_multi
#     def create(self, vals_list):
#         """
#         Override to intercept requests for the generic "Sick Leave" type
#         and convert them into the correctly tiered pay type.
#         """
#         request_type = self.env.ref('ahadu_hr_leave.ahadu_sick_leave_request', raise_if_not_found=False)
#         # Ensure the data file has been loaded before proceeding
#         if not request_type:
#             return super(HrLeave, self).create(vals_list)

#         pay_100_type = self.env.ref('ahadu_hr_leave.ahadu_sick_leave_100_pay')
#         pay_50_type = self.env.ref('ahadu_hr_leave.ahadu_sick_leave_50_pay')
#         pay_0_type = self.env.ref('ahadu_hr_leave.ahadu_sick_leave_0_pay')
        
#         sick_leave_types = [pay_100_type.id, pay_50_type.id, pay_0_type.id]

#         for vals in vals_list:
#             # Check if this is the sick leave type we need to process
#             if vals.get('holiday_status_id') == request_type.id:
#                 employee = self.env['hr.employee'].browse(vals.get('employee_id'))
                
#                 # Use from_string which handles False/None values gracefully
#                 request_start_date = fields.Date.from_string(vals.get('date_from'))
#                 request_end_date = fields.Date.from_string(vals.get('date_to'))
                
#                 # --- FIX: Add a check to ensure dates exist before proceeding ---
#                 # If the dates are not set yet, skip our logic and let Odoo create the draft record.
#                 if not employee or not request_start_date or not request_end_date:
#                     continue

#                 spell_start_date = employee.first_sick_leave_date_in_spell
                
#                 if not spell_start_date or (request_start_date - spell_start_date).days > 180:
#                     spell_start_date = request_start_date
#                     employee.write({'first_sick_leave_date_in_spell': spell_start_date})

#                 past_leaves = self.search([
#                     ('employee_id', '=', employee.id),
#                     ('state', '=', 'validate'),
#                     ('holiday_status_id', 'in', sick_leave_types),
#                     ('date_from', '>=', spell_start_date),
#                 ])
#                 days_already_taken = sum(leave.number_of_days for leave in past_leaves)

#                 request_duration = (request_end_date - request_start_date).days + 1
#                 if (days_already_taken + request_duration) > 180:
#                     raise ValidationError(_(
#                         "This sick leave request exceeds the maximum of 180 days in a sickness period. "
#                         "You have already taken %.2f days."
#                     ) % days_already_taken)

#                 if days_already_taken < 60:
#                     vals['holiday_status_id'] = pay_100_type.id
#                 elif days_already_taken < 120:
#                     vals['holiday_status_id'] = pay_50_type.id
#                 else:
#                     vals['holiday_status_id'] = pay_0_type.id
        
#         return super(HrLeave, self).create(vals_list)


#     def _recompute_allocations_balances(self):
#         allocations = self.env['hr.leave.allocation'].search([
#             ('employee_id', 'in', self.employee_id.ids),
#             ('holiday_status_id', 'in', self.holiday_status_id.ids)
#         ])
#         if allocations:
#             allocations._recompute_effective_balance()

#     def write(self, vals):
#         res = super().write(vals)
#         if 'state' in vals:
#             self._recompute_allocations_balances()
#         return res

# from ethiopian_date import EthiopianDateConverter

# from odoo import models, fields, api, _
# from odoo.exceptions import ValidationError
# from dateutil.relativedelta import relativedelta

# class HrLeave(models.Model):
#     _inherit = 'hr.leave' 

#     is_half_day = fields.Boolean(string="Half Day Request")

#     medical_certificate = fields.Binary(
#         string="Medical Certificate",
#         attachment=True,
#         copy=False,
#         help="Upload the medical certificate or other supporting documents here."
#     )
#     medical_certificate_filename = fields.Char(string="Certificate Filename", copy=False)


#     # --- NEW ETHIOPIAN CALENDAR FIELDS ---
#     ethiopian_date_from = fields.Char(
#         string="From (Ethiopian)",
#         compute='_compute_ethiopian_dates',
#         store=False, # This is a display-only field
#     )
#     ethiopian_date_to = fields.Char(
#         string="To (Ethiopian)",
#         compute='_compute_ethiopian_dates',
#         store=False, # This is a display-only field
#     )

#     @api.depends('request_date_from', 'request_date_to')
#     def _compute_ethiopian_dates(self):
#         """
#         Computes the Ethiopian date representation for the start and end dates.
#         """
#         converter = EthiopianDateConverter()
#         for leave in self:
#             # Convert the start date
#             if leave.request_date_from:
#                 gregorian_from = leave.request_date_from
#                 et_date = converter.to_ethiopian(gregorian_from.year, gregorian_from.month, gregorian_from.day)
#                 # Format the output string nicely
#                 leave.ethiopian_date_from = f"{et_date[2]} {converter.MONTH_NAMES[et_date[1]]}, {et_date[0]}"
#             else:
#                 leave.ethiopian_date_from = False

#             # Convert the end date
#             if leave.request_date_to:
#                 gregorian_to = leave.request_date_to
#                 et_date = converter.to_ethiopian(gregorian_to.year, gregorian_to.month, gregorian_to.day)
#                 leave.ethiopian_date_to = f"{et_date[2]} {converter.MONTH_NAMES[et_date[1]]}, {et_date[0]}"
#             else:
#                 leave.ethiopian_date_to = False
# # end of ethiopian calendar logic

#     def _check_medical_certificate(self):
#         sick_leave_types = self.env['hr.leave.type'].search([
#             ('id', 'in', [
#                 self.env.ref('ahadu_hr_leave.ahadu_sick_leave_100_pay').id,
#                 self.env.ref('ahadu_hr_leave.ahadu_sick_leave_50_pay').id,
#                 self.env.ref('ahadu_hr_leave.ahadu_sick_leave_0_pay').id,
#             ])
#         ])
#         sick_leave_type_ids = sick_leave_types.ids
#         for leave in self:
#             if leave.holiday_status_id.id in sick_leave_type_ids and not leave.medical_certificate:
#                 raise ValidationError(_(
#                     "A medical certificate is required to approve this sick leave request. "
#                     "Please ask the employee to edit the request and upload the document."
#                 ))

#     # --- THIS IS THE FIX: Accept any arguments Odoo might pass ---
#     def action_approve(self, *args, **kwargs):
#         self._check_medical_certificate()
#         return super(HrLeave, self).action_approve(*args, **kwargs)

#     # --- THIS IS THE FIX: Accept any arguments Odoo might pass ---
#     def action_validate(self, *args, **kwargs):
#         self._check_medical_certificate()
#         return super(HrLeave, self).action_validate(*args, **kwargs)


#     @api.model_create_multi
#     def create(self, vals_list):
#         # ... (This method is correct and does not need changes) ...
#         # [The rest of your create method logic here]
#         request_type = self.env.ref('ahadu_hr_leave.ahadu_sick_leave_request', raise_if_not_found=False)
#         if not request_type:
#             return super(HrLeave, self).create(vals_list)
#         pay_100_type = self.env.ref('ahadu_hr_leave.ahadu_sick_leave_100_pay')
#         pay_50_type = self.env.ref('ahadu_hr_leave.ahadu_sick_leave_50_pay')
#         pay_0_type = self.env.ref('ahadu_hr_leave.ahadu_sick_leave_0_pay')
#         sick_leave_types_for_calc = [pay_100_type.id, pay_50_type.id, pay_0_type.id]
#         for vals in vals_list:
#             if vals.get('holiday_status_id') == request_type.id:
#                 employee = self.env['hr.employee'].browse(vals.get('employee_id'))
#                 request_start_date = fields.Date.from_string(vals.get('date_from'))
#                 request_end_date = fields.Date.from_string(vals.get('date_to'))
#                 if not employee or not request_start_date or not request_end_date:
#                     continue
#                 spell_start_date = employee.first_sick_leave_date_in_spell
#                 if not spell_start_date or (request_start_date - spell_start_date).days > 180:
#                     spell_start_date = request_start_date
#                     employee.write({'first_sick_leave_date_in_spell': spell_start_date})
#                 past_leaves = self.search([
#                     ('employee_id', '=', employee.id),
#                     ('state', '=', 'validate'),
#                     ('holiday_status_id', 'in', sick_leave_types_for_calc),
#                     ('date_from', '>=', spell_start_date),
#                 ])
#                 days_already_taken = sum(leave.number_of_days for leave in past_leaves)
#                 request_duration = (request_end_date - request_start_date).days + 1
#                 if (days_already_taken + request_duration) > 180:
#                     raise ValidationError(_("This sick leave request exceeds the maximum of 180 days in a sickness period. You have already taken %.2f days.") % days_already_taken)
#                 if days_already_taken < 60:
#                     vals['holiday_status_id'] = pay_100_type.id
#                 elif days_already_taken < 120:
#                     vals['holiday_status_id'] = pay_50_type.id
#                 else:
#                     vals['holiday_status_id'] = pay_0_type.id
#         return super(HrLeave, self).create(vals_list)

#     def _recompute_allocations_balances(self):
#         allocations = self.env['hr.leave.allocation'].search([
#             ('employee_id', 'in', self.employee_id.ids),
#             ('holiday_status_id', 'in', self.holiday_status_id.ids)
#         ])
#         if allocations:
#             allocations._recompute_effective_balance()

#     def write(self, vals):
#         res = super().write(vals)
#         if 'state' in vals:
#             self._recompute_allocations_balances()
#         return res


from . import ethiopian_calendar
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta

class HrLeave(models.Model):
    _inherit = 'hr.leave' 

    is_half_day = fields.Boolean(string="Half Day Request")

    medical_certificate = fields.Binary(
        string="Medical Certificate",
        attachment=True,
        copy=False,
        help="Upload the medical certificate or other supporting documents here."
    )
    medical_certificate_filename = fields.Char(string="Certificate Filename", copy=False)

    ethiopian_date_from = fields.Char(
        string="From (Ethiopian)",
        compute='_compute_ethiopian_dates',
        store=False,
    )
    ethiopian_date_to = fields.Char(
        string="To (Ethiopian)",
        compute='_compute_ethiopian_dates',
        store=False,
    )

    @api.depends('request_date_from', 'request_date_to')
    def _compute_ethiopian_dates(self):
        """
        Computes the Ethiopian date representation for the start and end dates.
        """
        converter = ethiopian_calendar.EthiopianDateConverter()
        for leave in self:
            if leave.request_date_from:
                g_from = leave.request_date_from
                # The method returns a tuple (year, month, day)
                et_date = converter.to_ethiopian(g_from.year, g_from.month, g_from.day)
                # We can now safely access the elements by index
                leave.ethiopian_date_from = f"{et_date[2]} {converter.MONTH_NAMES[et_date[1]]}, {et_date[0]}"
            else:
                leave.ethiopian_date_from = False

            if leave.request_date_to:
                g_to = leave.request_date_to
                et_date = converter.to_ethiopian(g_to.year, g_to.month, g_to.day)
                leave.ethiopian_date_to = f"{et_date[2]} {converter.MONTH_NAMES[et_date[1]]}, {et_date[0]}"
            else:
                leave.ethiopian_date_to = False

                
    def _check_medical_certificate(self):
        # ... (This method is correct) ...
        sick_leave_types = self.env['hr.leave.type'].search([
            ('id', 'in', [
                self.env.ref('ahadu_hr_leave.ahadu_sick_leave_100_pay').id,
                self.env.ref('ahadu_hr_leave.ahadu_sick_leave_50_pay').id,
                self.env.ref('ahadu_hr_leave.ahadu_sick_leave_0_pay').id,
            ])
        ])
        sick_leave_type_ids = sick_leave_types.ids
        for leave in self:
            if leave.holiday_status_id.id in sick_leave_type_ids and not leave.medical_certificate:
                raise ValidationError(_("A medical certificate is required..."))

    def action_approve(self, *args, **kwargs):
        self._check_medical_certificate()
        return super(HrLeave, self).action_approve(*args, **kwargs)

    def action_validate(self, *args, **kwargs):
        self._check_medical_certificate()
        return super(HrLeave, self).action_validate(*args, **kwargs)

    @api.model_create_multi
    def create(self, vals_list):
        # ... (This method is correct) ...
        request_type = self.env.ref('ahadu_hr_leave.ahadu_sick_leave_request', raise_if_not_found=False)
        if not request_type: return super(HrLeave, self).create(vals_list)
        pay_100_type = self.env.ref('ahadu_hr_leave.ahadu_sick_leave_100_pay')
        pay_50_type = self.env.ref('ahadu_hr_leave.ahadu_sick_leave_50_pay')
        pay_0_type = self.env.ref('ahadu_hr_leave.ahadu_sick_leave_0_pay')
        sick_leave_types_for_calc = [pay_100_type.id, pay_50_type.id, pay_0_type.id]
        for vals in vals_list:
            if vals.get('holiday_status_id') == request_type.id:
                employee = self.env['hr.employee'].browse(vals.get('employee_id'))
                request_start_date = fields.Date.from_string(vals.get('date_from'))
                request_end_date = fields.Date.from_string(vals.get('date_to'))
                if not employee or not request_start_date or not request_end_date: continue
                spell_start_date = employee.first_sick_leave_date_in_spell
                if not spell_start_date or (request_start_date - spell_start_date).days > 180:
                    spell_start_date = request_start_date
                    employee.write({'first_sick_leave_date_in_spell': spell_start_date})
                past_leaves = self.search([('employee_id', '=', employee.id), ('state', '=', 'validate'), ('holiday_status_id', 'in', sick_leave_types_for_calc), ('date_from', '>=', spell_start_date)])
                days_already_taken = sum(leave.number_of_days for leave in past_leaves)
                request_duration = (request_end_date - request_start_date).days + 1
                if (days_already_taken + request_duration) > 180: raise ValidationError(_("This sick leave request exceeds the maximum..."))
                if days_already_taken < 60: vals['holiday_status_id'] = pay_100_type.id
                elif days_already_taken < 120: vals['holiday_status_id'] = pay_50_type.id
                else: vals['holiday_status_id'] = pay_0_type.id
        return super(HrLeave, self).create(vals_list)

    def _recompute_allocations_balances(self):
        # ... (This method is correct) ...
        allocations = self.env['hr.leave.allocation'].search([('employee_id', 'in', self.employee_id.ids), ('holiday_status_id', 'in', self.holiday_status_id.ids)])
        if allocations: allocations._recompute_effective_balance()

    def write(self, vals):
        # ... (This method is correct) ...
        res = super().write(vals)
        if 'state' in vals: self._recompute_allocations_balances()
        return res