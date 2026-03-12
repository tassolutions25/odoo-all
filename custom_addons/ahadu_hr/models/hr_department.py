from odoo import models, fields, api
from collections import defaultdict


class Department(models.Model):
    _inherit = "hr.department"

    division_ids = fields.One2many("hr.division", "department_id", string="Divisions")
    division_count = fields.Integer(
        compute="_compute_division_count", string="Division Count"
    )

    cost_center_id = fields.Many2one(
        "hr.cost.center",
        string="Cost Center",
        tracking=True,
        ondelete="set null",
        help="Default Cost Center for employees in this department.",
    )

    def _compute_division_count(self):
        for department in self:
            department.division_count = self.env["hr.division"].search_count(
                [("department_id", "=", department.id)]
            )

    def action_view_divisions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Divisions",
            "res_model": "hr.division",
            "view_mode": "list,form",
            "domain": [("department_id", "=", self.id)],
            "context": {"default_department_id": self.id},
        }

    @api.model
    def get_structural_hierarchy(self, filters=None):
        """
        Builds the structural organogram based on the hr.organogram.node model.
        """
        Employee = self.env["hr.employee"]
        OrgNode = self.env["hr.organogram.node"]

        # Cache all active employees by their job_id for performance.
        employees_by_job = defaultdict(list)
        all_employees = Employee.search_read(
            [("job_id", "!=", False), ("active", "=", True)],
            ["id", "name", "job_id"],
        )
        for emp in all_employees:
            employees_by_job[emp["job_id"][0]].append(emp)

        def get_employee_info(job_id):
            if job_id in employees_by_job:
                # If multiple employees have the same job, take the first one.
                emp = employees_by_job[job_id][0]
                return {
                    "name": emp["name"],
                    "imageUrl": f"/web/image/hr.employee/{emp['id']}/avatar_128",
                }
            return None

        def get_subordinates_count(job_id):
            # Find the employee (manager) holding this job position.
            manager = Employee.search(
                [("job_id", "=", job_id), ("active", "=", True)], limit=1
            )
            if not manager:
                return 0
            # Count the number of active employees who report directly to this manager.
            return Employee.search_count(
                [
                    ("parent_id", "=", manager.id),
                    ("active", "=", True),
                ]
            )

        def build_tree_recursive(organogram_nodes):
            tree = []
            for node in organogram_nodes:
                employee_info = (
                    get_employee_info(node.job_id.id) if node.job_id else None
                )

                # Determine the name, title, and image for the card.
                if employee_info:
                    display_name = employee_info.get("name")
                    display_title = node.job_id.name if node.job_id else "Unit"
                    image_url = employee_info.get("imageUrl")
                    sub_count = get_subordinates_count(node.job_id.id)
                else:
                    display_name = node.name
                    display_title = (
                        node.job_id.name if node.job_id else "Unit / Department"
                    )
                    image_url = (
                        "/ahadu_hr/static/src/img/c-level.png"  # Generic placeholder
                    )
                    sub_count = 0

                node_data = {
                    "id": f"org_node_{node.id}",
                    "name": display_name,
                    "job_title": display_title,
                    "imageUrl": image_url,
                    "subordinates_count": sub_count,
                    "is_expanded": False,
                    "children": build_tree_recursive(node.child_ids),
                }

                tree.append(node_data)
            return tree

        # Start building the tree from the root nodes (those with no parent).
        root_nodes = OrgNode.search([("parent_id", "=", False)])
        hierarchy = build_tree_recursive(root_nodes)

        # Set the top-level nodes to be expanded by default for a better initial view.
        for root_node in hierarchy:
            root_node["is_expanded"] = True

        return {"hierarchy": hierarchy}
