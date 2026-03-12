from odoo import models, fields, api, _

class HrEmployeeDisciplinary(models.Model):
    _name = 'hr.employee.disciplinary'
    _description = 'Employee Disciplinary Action'
    _order = 'action_date desc'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    action_date = fields.Date(string='Action Date', required=True, default=fields.Date.today)
    
    action_type = fields.Selection([
        ('warning', 'Warning'),
        ('suspension', 'Suspension'),
        ('termination', 'Termination'),
        ('fine', 'Fine'),
    ], string='Action Type', required=True)
    
    violation = fields.Text(string='Violation Description', required=True)
    action_taken = fields.Text(string='Action Taken', required=True)
    duration = fields.Integer(string='Duration (Days)', help="For suspension actions")
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='State', default='draft')
    
    activity_id = fields.Many2one('hr.employee.activity', string='Activity Record')

    @api.model
    def create(self, vals):
        disciplinary = super().create(vals)
        # Create activity record
        activity_vals = {
            'employee_id': disciplinary.employee_id.id,
            'activity_type': 'disciplinary',
            'date': disciplinary.action_date,
            'disciplinary_id': disciplinary.id,
            'description': f"Disciplinary Action - {disciplinary.action_type}",
        }
        disciplinary.activity_id = self.env['hr.employee.activity'].create(activity_vals)
        return disciplinary

    def action_activate(self):
        self.state = 'active'
        if self.activity_id:
            self.activity_id.action_submit()

    def action_complete(self):
        self.state = 'completed'
        if self.activity_id:
            self.activity_id.action_approve()

    def action_cancel(self):
        self.state = 'cancelled'
        if self.activity_id:
            self.activity_id.action_reject()