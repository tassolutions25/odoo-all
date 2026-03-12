from odoo import models, fields


class HrEmployeeFamily(models.Model):
    _name = "hr.employee.family"
    _description = "Employee Family Member"
    _order = "id"

    employee_id = fields.Many2one(
        "hr.employee", string="Employee", ondelete="cascade", required=True
    )
    relationship = fields.Selection(
        [
            ("mother", "Mother"),
            ("father", "Father"),
            ("sister", "Sister"),
            ("brother", "Brother"),
            ("aunt", "Aunt"),
            ("uncle", "Uncle"),
            ("son", "Son"),
            ("daughter", "Daughter"),
            ("spouse", "Spouse"),
            ("other", "Other"),
        ],
        string="Relationship",
        required=True,
    )
    full_name = fields.Char(string="Full Name", required=True)
    contact_number = fields.Char(string="Contact Number")
    gender = fields.Selection(
        [("male", "Male"), ("female", "Female")], string="Gender", required=True
    )
    nationality_id = fields.Many2one("res.country", string="Nationality", required=True)
    dependent = fields.Boolean(string="Dependent?")
    insured = fields.Boolean(string="Insured?")
