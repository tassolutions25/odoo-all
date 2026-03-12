# from odoo import api, models
# from odoo.tools.safe_eval import safe_eval


# class HrSalaryRule(models.Model):
#     _inherit = "hr.salary.rule"

#     def _get_grade_override(self, localdict):
#         employee = localdict.get("employee")
#         contract = localdict.get("contract")
#         if not employee and contract:
#             employee = contract.employee_id
#         grade = employee and employee.grade_id
#         if not grade:
#             return None
#         return self.env["hr.grade.allowance"].sudo().search(
#             [
#                 ("grade_id", "=", grade.id),
#                 ("rule_id", "=", self.id),
#                 ("active", "=", True),
#             ],
#             limit=1,
#         )

#     def _compute_rule_fix(self, localdict):
#         override = self._get_grade_override(localdict)
#         if override and override.amount_type == "fix":
#             return {
#                 "name": self.name,
#                 "quantity": float(safe_eval(self.quantity, localdict)),
#                 "rate": 100.0,
#                 "amount": override.amount_fix,
#             }
#         return super()._compute_rule_fix(localdict)

#     def _compute_rule_percentage(self, localdict):
#         override = self._get_grade_override(localdict)
#         if override and override.amount_type == "percentage":
#             return {
#                 "name": self.name,
#                 "quantity": float(safe_eval(self.quantity, localdict)),
#                 "rate": override.amount_percentage,
#                 "amount": float(safe_eval(self.amount_percentage_base, localdict)),
#             }
#         return super()._compute_rule_percentage(localdict) 