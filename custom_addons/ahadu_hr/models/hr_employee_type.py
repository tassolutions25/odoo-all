# ahadu_hr/models/hr_employee_type.py

from odoo import models, fields, api


class HrEmployeeType(models.Model):
    _name = "hr.employee.type"
    _description = "Employee Type"
    _order = "name"

    name = fields.Char(string="Employee Type", required=True)
    code = fields.Char(string="Code", required=True)
    job_ids = fields.Many2many("hr.job", string="Applicable Job Positions")

    _sql_constraints = [
        ("code_unique", "unique(code)", "The code of the employee type must be unique!"),
    ]

    @api.constrains("job_ids")
    def _check_exclusive_jobs(self):
        for record in self:
            for job in record.job_ids:
                other_types = self.search([("id", "!=", record.id), ("job_ids", "in", job.id)])
                if other_types:
                    raise models.ValidationError(
                        f"The job position '{job.name}' is already assigned to another employee type: {other_types[0].name}."
                    )
