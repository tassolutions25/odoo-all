from ..models import ethiopian_calendar
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, time

class LeaveRequestWizard(models.TransientModel):
    _name = 'ahadu.leave.request.wizard'
    _description = 'Leave Request Wizard'

    employee_id = fields.Many2one('hr.employee', string="Employee", readonly=True, default=lambda self: self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1))
    
    # This field is for allocated leaves
    allocation_id = fields.Many2one(
        'hr.leave.allocation', string="Leave Balance",
        domain="[('employee_id', '=', employee_id), ('state', '=', 'validate'), ('effective_remaining_leaves', '>', 0)]"
    )
    # This field is for unallocated leaves
    holiday_status_id = fields.Many2one(
        'hr.leave.type', string="Leave Type", required=False,
    )
    
    request_date_from = fields.Date(string="Start Date", required=True, default=fields.Date.context_today)
    request_date_to = fields.Date(string="End Date", required=True, default=fields.Date.context_today)
    name = fields.Char(string="Description")
    number_of_days = fields.Float(string="Requested (Days)", readonly=False) # Must not be readonly
    
    # We now have TWO separate onchange methods for clarity and robustness
    # attachment_mandatory_allocated = fields.Boolean(related='allocation_id.holiday_status_id.support_document', readonly=True)
    # attachment_mandatory_unallocated = fields.Boolean(related='holiday_status_id.support_document', readonly=True)
    
    # attachment_ids = fields.Many2many('ir.attachment', string="Supporting Document")

    is_attachment_mandatory = fields.Boolean(string="Attachment is Mandatory", compute='_compute_is_attachment_mandatory')
    attachment_ids = fields.Many2many('ir.attachment', string="Supporting Document")

    @api.depends('allocation_id', 'holiday_status_id')
    def _compute_is_attachment_mandatory(self):
        """ A single method to determine if an attachment is required. """
        for wizard in self:
            leave_type = wizard.allocation_id.holiday_status_id if wizard.allocation_id else wizard.holiday_status_id
            wizard.is_attachment_mandatory = leave_type.support_document if leave_type else False


    # Ethiopian date fields (display-only)
    ethiopian_date_from = fields.Char(string="From (Ethiopian)", compute='_compute_ethiopian_dates', readonly=True)
    ethiopian_date_to = fields.Char(string="To (Ethiopian)", compute='_compute_ethiopian_dates', readonly=True)

    @api.depends('request_date_from', 'request_date_to')
    def _compute_ethiopian_dates(self):
        """
        Computes the Ethiopian date representation for the wizard's dates.
        """
        # This logic is copied from our main hr.leave model
        converter = ethiopian_calendar.EthiopianDateConverter()
        for wizard in self:
            if wizard.request_date_from:
                g_from = wizard.request_date_from
                et_date = converter.to_ethiopian(g_from.year, g_from.month, g_from.day)
                wizard.ethiopian_date_from = f"{et_date[2]} {converter.MONTH_NAMES[et_date[1]]}, {et_date[0]}"
            else:
                wizard.ethiopian_date_from = False

            if wizard.request_date_to:
                g_to = wizard.request_date_to
                et_date = converter.to_ethiopian(g_to.year, g_to.month, g_to.day)
                wizard.ethiopian_date_to = f"{et_date[2]} {converter.MONTH_NAMES[et_date[1]]}, {et_date[0]}"
            else:
                wizard.ethiopian_date_to = False
    # --- END OF ETHIOPIAN CALENDAR CONVERSION   ---

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        res = super(LeaveRequestWizard, self).fields_get(allfields, attributes)
        # We find the definition of our field
        if 'holiday_status_id' in res:
            # We call our helper method to get the list of allowed IDs
            allowed_leave_type_ids = self.env['hr.leave.type']._get_contextual_leave_types().ids
            # And we dynamically inject the correct domain
            res['holiday_status_id']['domain'] = [('id', 'in', allowed_leave_type_ids)]
        return res

    @api.model
    def _get_available_leave_types(self):
        # We only want unallocated types in this specific dropdown
        unallocated_types = self.env['hr.leave.type'].search([
            ('employee_requests', '=', 'yes'),
            ('requires_allocation', '=', False)
        ])
        return unallocated_types.ids

    @api.onchange('request_date_from', 'request_date_to', 'employee_id')
    def _onchange_dates(self):
        """
        Calculates the number of WORKING days using the employee's calendar.
        """
        if self.request_date_from and self.request_date_to and self.employee_id:
            date_from_dt = datetime.combine(self.request_date_from, time.min)
            date_to_dt = datetime.combine(self.request_date_to, time.max)
            
            calendar = self.employee_id.resource_calendar_id
            if calendar:
                work_hours = calendar.get_work_hours_count(date_from_dt, date_to_dt)
                hours_per_day = calendar.hours_per_day or 8
                self.number_of_days = work_hours / hours_per_day if hours_per_day else 0
            else:
                self.number_of_days = (self.request_date_to - self.request_date_from).days + 1
        else:
            self.number_of_days = 0

    def action_submit_request(self):
        self.ensure_one()
        
        # This logic is now simpler and more robust
        leave_type = self.allocation_id.holiday_status_id if self.allocation_id else self.holiday_status_id
        if not leave_type:
            raise UserError(_("You must select a Leave Type or a Leave Balance."))

        if self.number_of_days <= 0:
            raise UserError(_("The requested leave duration must be positive."))
            
        if leave_type.support_document and not self.attachment_ids:
            raise UserError(_("You must attach a supporting document for this type of leave."))

        leave_values = {
            'holiday_status_id': leave_type.id, 'employee_id': self.employee_id.id,
            'request_date_from': self.request_date_from, 'request_date_to': self.request_date_to,
            'name': self.name, 
            'allocation_id': self.allocation_id.id if self.allocation_id else False,
        }
        new_leave = self.env['hr.leave'].create(leave_values)

        if self.attachment_ids:
            new_leave.message_post(attachment_ids=self.attachment_ids.ids)

        return {'type': 'ir.actions.act_window_close'}