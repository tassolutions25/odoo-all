from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HrDivision(models.Model):
    _name = "hr.division"
    _description = "HR Division"
    _order = "sequence, name"
    _rec_name = "name"
    _check_company_auto = True

    name = fields.Char(string="Division Name", required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    department_id = fields.Many2one(
        "hr.department", string="Head Department", required=True, ondelete="cascade"
    )
    manager_id = fields.Many2one(
        "hr.employee",
        string="Division Manager",
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="department_id.company_id",
        store=True,
        readonly=True,
    )

    # Hierarchy
    parent_id = fields.Many2one(
        "hr.division", string="Parent Division", ondelete="restrict"
    )
    child_ids = fields.One2many("hr.division", "parent_id", string="Child Divisions")

    description = fields.Text(string="Description")
    organogram_node_id = fields.Many2one(
        "hr.organogram.node", string="Organogram Node", copy=False, ondelete="set null"
    )
    _sql_constraints = [
        (
            "name_department_uniq",
            "unique(name, department_id)",
            "A division with this name already exists in this department.",
        )
    ]

    @api.constrains("parent_id")
    def _check_parent_recursion(self):
        if not self._check_recursion():
            raise ValidationError(_("You cannot create recursive divisions."))

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get("no_sync"):
            return super().create(vals_list)

        divisions = super(HrDivision, self.with_context(no_sync=True)).create(vals_list)
        for division in divisions:
            parent_node_id = False
            # Find parent node from parent division or parent department manager's job
            if division.parent_id and division.parent_id.organogram_node_id:
                parent_node_id = division.parent_id.organogram_node_id.id
            elif (
                division.department_id
                and division.department_id.manager_id
                and division.department_id.manager_id.job_id
            ):
                parent_node = self.env["hr.organogram.node"].search(
                    [("job_id", "=", division.department_id.manager_id.job_id.id)],
                    limit=1,
                )
                if parent_node:
                    parent_node_id = parent_node.id

            node = (
                self.env["hr.organogram.node"]
                .with_context(no_sync=True)
                .create(
                    {
                        "name": division.name,
                        "node_type": "team",  # 'Team/Division' type
                        "parent_id": parent_node_id,
                        "division_id": division.id,  # Link back to the division
                    }
                )
            )
            division.with_context(no_sync=True).organogram_node_id = node.id
        return divisions

    def write(self, vals):
        if self.env.context.get("no_sync"):
            return super().write(vals)

        res = super().write(vals)
        for division in self:
            if division.organogram_node_id:
                node_vals = {}
                if "name" in vals:
                    node_vals["name"] = vals["name"]
                if "parent_id" in vals:
                    parent_division = (
                        self.browse(vals["parent_id"])
                        if vals.get("parent_id")
                        else False
                    )
                    parent_node_id = (
                        parent_division.organogram_node_id.id
                        if parent_division and parent_division.organogram_node_id
                        else False
                    )
                    node_vals["parent_id"] = parent_node_id

                if node_vals:
                    division.organogram_node_id.with_context(no_sync=True).write(
                        node_vals
                    )
        return res

    def unlink(self):
        if self.env.context.get("no_sync"):
            return super().unlink()

        nodes_to_delete = self.mapped("organogram_node_id")
        res = super().unlink()
        nodes_to_delete.with_context(no_sync=True).unlink()
        return res
