# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class HrEmployeeTraining(models.Model):
    _name = "hr.employee.training"
    _description = "Employee Training History"
    _order = "end_date desc, id desc"

    employee_id = fields.Many2one(
        "hr.employee", string="Employee", required=True, ondelete="cascade"
    )
    onboarding_id = fields.Many2one(
        'hr.employee.onboarding', string="Onboarding Request", ondelete="cascade"
    )
    name = fields.Char(string="Training Name", required=True)
    trainer_company = fields.Char(string="Training Institution")
    start_date = fields.Date(string="Start Date")
    end_date = fields.Date(string="End Date")
    certification_attachment = fields.Binary(string="Certificate")
    certification_filename = fields.Char(string="Certificate Filename")

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for record in self:
            if record.start_date and record.end_date and record.start_date > record.end_date:
                raise ValidationError(_('The training end date cannot be earlier than the start date.'))
            
    @api.constrains('certification_filename')
    def _check_file_extension(self):
        for record in self:
            if record.certification_filename and not record.certification_filename.lower().endswith(('.pdf', '.png')):
                raise ValidationError(_("Invalid file format for certificate. Please upload a PDF or PNG file."))