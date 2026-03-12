# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class HrBenefitType(models.Model):
    """Defines the master list of all possible benefit types/allowances."""

    _name = "hr.benefit.type"
    _description = "Benefit Type"
    _order = "sequence, name"

    name = fields.Char(string="Benefit Name", required=True, translate=True)
    code = fields.Char(
        string="Code",
        required=True,
        help="A unique technical code for this benefit (e.g., HOUSE_ALLOW, FUEL).",
    )
    value_type = fields.Selection(
        [
            ("fixed", "Fixed Amount"),
            ("percentage", "Percentage of Base Salary"),
            ("in_kind", "In-Kind / Descriptive"),
        ],
        string="Value Type",
        default="fixed",
        required=True,
        help="Determines how the benefit's value is recorded.",
    )
    sequence = fields.Integer(default=10)

    _sql_constraints = [
        ("code_uniq", "unique (code)", "The Benefit Code must be unique."),
        ("name_uniq", "unique (name)", "The Benefit Name must be unique."),
    ]


class HrBenefitPackage(models.Model):
    """A collection of benefits assigned to one or more job positions."""

    _name = "hr.benefit.package"
    _description = "Benefit Package"

    name = fields.Char(string="Package Name", required=True)
    job_ids = fields.Many2many(
        "hr.job",
        string="Applicable Job Positions",
        help="This benefit package will apply to all employees holding these job positions.",
    )
    line_ids = fields.One2many(
        "hr.benefit.package.line", "package_id", string="Benefit Lines"
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("name_uniq", "unique(name)", "The Package Name must be unique."),
    ]

class HrBenefitPackageLine(models.Model):
    """Defines the value of a specific benefit within a package."""

    _name = "hr.benefit.package.line"
    _description = "Benefit Package Line"
    _rec_name = "benefit_type_id"

    package_id = fields.Many2one(
        "hr.benefit.package", string="Package", required=True, ondelete="cascade"
    )
    benefit_type_id = fields.Many2one(
        "hr.benefit.type", string="Benefit", required=True
    )
    value_type = fields.Selection(related="benefit_type_id.value_type", readonly=True)

    # Value fields - only one will be used depending on the value_type
    value_fixed = fields.Float(string="Fixed Amount", digits="Product Price")
    value_percentage = fields.Float(string="Percentage (%)")
    value_in_kind = fields.Text(string="Description / Rule")

    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        default=lambda self: self.env.company.currency_id,
        required=True,
    )
