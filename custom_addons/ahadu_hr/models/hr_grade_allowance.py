# from odoo import models, fields, api


# class HrGradeAllowance(models.Model):
#     _name = "hr.grade.allowance"
#     _description = "Grade Salary Rule Amount"
#     _order = "sequence, id"

#     name = fields.Char(string="Description")
#     sequence = fields.Integer(default=10)
#     grade_id = fields.Many2one(
#         "hr.grade",
#         string="Grade",
#         required=True,
#         ondelete="cascade",
#         index=True,
#     )
#     rule_id = fields.Many2one(
#         "hr.salary.rule",
#         string="Salary Rule",
#         required=True,
#         ondelete="restrict",
#         domain=[("active", "=", True)],
#         index=True,
#     )
#     amount_type = fields.Selection(
#         [
#             ("fix", "Fixed Amount"),
#             ("percentage", "Percentage (%)"),
#         ],
#         string="Amount Type",
#         required=True,
#         default="fix",
#     )
#     amount_fix = fields.Monetary(string="Fixed Amount", currency_field="currency_id")
#     amount_percentage = fields.Float(string="Percentage (%)")
#     currency_id = fields.Many2one(
#         "res.currency",
#         string="Currency",
#         default=lambda self: self.env.company.currency_id,
#     )
#     active = fields.Boolean(default=True)

#     _sql_constraints = [
#         (
#             "grade_rule_unique",
#             "unique(grade_id, rule_id)",
#             "You already defined an amount for this rule on this grade.",
#         )
#     ]

#     @api.onchange("amount_type")
#     def _onchange_amount_type(self):
#         for rec in self:
#             if rec.amount_type == "fix":
#                 rec.amount_percentage = 0.0
#             else:
#                 rec.amount_fix = 0.0 