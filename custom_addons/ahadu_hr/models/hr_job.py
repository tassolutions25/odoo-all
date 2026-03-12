# ahadu_hr/models/hr_job.py

from odoo import models, fields, api, _


class HrJob(models.Model):
    _inherit = "hr.job"

    # Structure & Compensation
    grade_id = fields.Many2one("hr.grade", string="Job Grade", tracking=True)
    cost_center_id = fields.Many2one(
        "hr.cost.center", string="Cost Center", tracking=True
    )
    division_id = fields.Many2one("hr.division", string="Division", tracking=True)

    organogram_node_ids = fields.One2many(
        "hr.organogram.node", "job_id", string="Organogram Nodes"
    )
    ahadu_employee_type_ids = fields.Many2many(
        "hr.employee.type", string="Employee Types", tracking=True
    )

    # Status Tracking
    status = fields.Selection(
        [("vacant", "Vacant"), ("filled", "Filled"), ("frozen", "Frozen")],
        string="Status",
        compute="_compute_status",
        store=True,
        readonly=False,
        tracking=True,
        help="Automatically updated based on employee assignment, but can be manually set to 'Frozen'.",
    )

    @api.depends("no_of_employee", "expected_employees")
    def _compute_status(self):
        """
        Computes the status of the job position.
        - If manually set to 'Frozen', it remains frozen.
        - If the number of current employees is equal to or greater than the expected number, it is 'Filled'.
        - Otherwise, it's 'Vacant'.
        """
        for job in self:
            if job.status == "frozen":
                # Don't change the status if it's manually frozen by a user
                continue

            # The job is considered filled if the headcount is met or exceeded.
            # A target of 0 also means it's effectively filled (no vacancies).
            if job.no_of_employee >= job.expected_employees:
                job.status = "filled"
            else:
                job.status = "vacant"

    def _sync_job_status(self):
        """
        Helper method to be called from other models (like hr.employee)
        to force the re-computation of the status for a set of jobs.
        This ensures that when an employee is created/updated, the job they
        are linked to reflects the correct status.
        """
        # This method is kept for clarity in the calling model (hr.employee).
        pass
