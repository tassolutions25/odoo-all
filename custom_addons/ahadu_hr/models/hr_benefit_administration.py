# from odoo import models, fields, api, _
# from odoo.exceptions import ValidationError
# from datetime import date


# # ==================================
# # 1. Model to Define Benefit Types
# # ==================================
# class HrBenefit(models.Model):
#     _name = "hr.benefit"
#     _description = "Benefit Type"
#     _order = "name"

#     name = fields.Char(string="Benefit Name", required=True)
#     code = fields.Char(
#         string="Code", help="A short code for this benefit, e.g., MED, EYE."
#     )
#     benefit_type = fields.Selection(
#         [
#             ("cash", "Cash Allowance"),
#             ("service", "Service/In-Kind"),
#             ("reimbursement", "Reimbursement"),
#         ],
#         string="Type",
#         default="reimbursement",
#         required=True,
#     )
#     description = fields.Text(string="Description")
#     active = fields.Boolean(default=True)

#     _sql_constraints = [
#         ("name_uniq", "unique (name)", "Benefit name must be unique."),
#         ("code_uniq", "unique (code)", "Benefit code must be unique."),
#     ]


# # ============================================
# # 2. Model for Benefit Plans (e.g., Management Plan)
# # ============================================
# class HrBenefitPlan(models.Model):
#     _name = "hr.benefit.plan"
#     _description = "Benefit Plan"
#     _order = "name"

#     name = fields.Char(string="Plan Name", required=True)
#     grade_ids = fields.Many2many("hr.grade", string="Applicable Grades", required=True)
#     line_ids = fields.One2many(
#         "hr.benefit.plan.line", "plan_id", string="Benefit Lines"
#     )
#     active = fields.Boolean(default=True)


# # =======================================================
# # 3. Model for Plan Lines (Rules for each benefit in a plan)
# # =======================================================
# class HrBenefitPlanLine(models.Model):
#     _name = "hr.benefit.plan.line"
#     _description = "Benefit Plan Line"
#     _order = "plan_id, benefit_id"
#     _rec_name = "display_name"

#     display_name = fields.Char(
#         string="Display Name", compute="_compute_display_name", store=True
#     )
#     plan_id = fields.Many2one(
#         "hr.benefit.plan", string="Plan", required=True, ondelete="cascade"
#     )
#     benefit_id = fields.Many2one("hr.benefit", string="Benefit", required=True)
#     limit_amount = fields.Float(
#         string="Limit Amount",
#         digits="Product Price",
#         help="The maximum amount allowed for this benefit.",
#     )
#     frequency = fields.Selection(
#         [
#             ("yearly", "Yearly"),
#             ("every_two_years", "Every 2 Years"),
#             ("one_time", "One-Time"),
#         ],
#         string="Frequency",
#         default="yearly",
#         required=True,
#     )

#     @api.depends("benefit_id.name")
#     def _compute_display_name(self):
#         for line in self:
#             line.display_name = line.benefit_id.name or ""

#     _sql_constraints = [
#         (
#             "plan_benefit_uniq",
#             "unique (plan_id, benefit_id)",
#             "Each benefit can only be defined once per plan.",
#         ),
#     ]


# # =======================================
# # 4. Model for Employee Benefit Claims
# # =======================================
# class HrBenefitClaim(models.Model):
#     _name = "hr.benefit.claim"
#     _description = "Employee Benefit Claim"
#     _order = "claim_date desc"
#     _inherit = ["mail.thread", "mail.activity.mixin"]

#     name = fields.Char(string="Description", required=True)
#     employee_id = fields.Many2one(
#         "hr.employee", string="Employee", required=True, tracking=True
#     )
#     benefit_plan_id = fields.Many2one(related="employee_id.benefit_plan_id", store=True)
#     benefit_line_id = fields.Many2one(
#         "hr.benefit.plan.line",
#         string="Benefit Type",
#         required=True,
#         domain="[('plan_id', '=', benefit_plan_id)]",
#     )
#     benefit_id = fields.Many2one(related="benefit_line_id.benefit_id", store=True)

#     claim_date = fields.Date(
#         string="Claim Date",
#         default=fields.Date.context_today,
#         required=True,
#         tracking=True,
#     )
#     claim_amount = fields.Float(
#         string="Claim Amount", required=True, tracking=True, digits="Product Price"
#     )

#     # Specific field for Eyeglass benefit
#     eyeglass_purchase_date = fields.Date(string="Eyeglass Purchase Date")

#     state = fields.Selection(
#         [
#             ("draft", "Draft"),
#             ("submitted", "Submitted"),
#             ("approved", "Approved"),
#             ("paid", "Paid"),
#             ("rejected", "Rejected"),
#         ],
#         string="Status",
#         default="draft",
#         tracking=True,
#     )

#     attachment_ids = fields.Many2many("ir.attachment", string="Attachments")

#     @api.constrains("claim_amount", "state")
#     def _check_claim_limit(self):
#         for claim in self.filtered(lambda c: c.state == "approved"):
#             plan_line = claim.benefit_line_id
#             if not plan_line or plan_line.limit_amount <= 0:
#                 continue

#             # Determine date range based on frequency
#             today = fields.Date.today()
#             if plan_line.frequency == "yearly":
#                 fiscalyear_dates = self.env.company.compute_fiscalyear_dates(today)
#                 start_date, end_date = (
#                     fiscalyear_dates["date_from"],
#                     fiscalyear_dates["date_to"],
#                 )
#             elif plan_line.frequency == "every_two_years":
#                 start_date = (
#                     date(today.year - 1, 1, 1)
#                     if today.year % 2 == 1
#                     else date(today.year, 1, 1)
#                 )
#                 end_date = date(start_date.year + 1, 12, 31)
#             else:
#                 continue

#             # Sum up previous approved claims in the period
#             approved_claims = self.search(
#                 [
#                     ("employee_id", "=", claim.employee_id.id),
#                     ("benefit_line_id", "=", plan_line.id),
#                     ("state", "=", "approved"),
#                     ("claim_date", ">=", start_date),
#                     ("claim_date", "<=", end_date),
#                     ("id", "!=", claim.id),
#                 ]
#             )
#             total_claimed = (
#                 sum(approved_claims.mapped("claim_amount")) + claim.claim_amount
#             )

#             if total_claimed > plan_line.limit_amount:
#                 raise ValidationError(
#                     _(
#                         "This claim of %.2f exceeds the benefit limit of %.2f. The employee has already claimed %.2f in this period.",
#                         claim.claim_amount,
#                         plan_line.limit_amount,
#                         total_claimed - claim.claim_amount,
#                     )
#                 )

#     def action_submit(self):
#         self.write({"state": "submitted"})

#     def action_approve(self):
#         self.write({"state": "approved"})

#     def action_set_to_paid(self):
#         self.write({"state": "paid"})

#     def action_reject(self):
#         self.write({"state": "rejected"})

#     def action_reset_to_draft(self):
#         self.write({"state": "draft"})
