from odoo import models, api

class HrLeaveType(models.Model):
    _inherit = 'hr.leave.type'

    @api.model
    def _get_contextual_leave_types(self):
        """
        [DEFINITIVE FIX] This is now a standalone helper method. It searches for all
        leave types a user can request and then applies our custom gender filtering.
        """
        leave_types = self.search([('employee_requests', '=', 'yes')])
        
        employee = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        if not employee:
            return leave_types

        paternity_type = self.env.ref('ahadu_hr_leave.ahadu_leave_type_paternity', raise_if_not_found=False)
        maternity_type = self.env.ref('ahadu_hr_leave.ahadu_leave_type_maternity', raise_if_not_found=False)
        
        if employee.gender != 'male' and paternity_type:
            leave_types = leave_types.filtered(lambda lt: lt.id != paternity_type.id)
            
        if employee.gender != 'female' and maternity_type:
            leave_types = leave_types.filtered(lambda lt: lt.id != maternity_type.id)
                
        return leave_types