from odoo import models, fields, api


class HrOrganogramNode(models.Model):
    """
    This model defines the static structure of the company's organogram.
    Each record represents a position or unit in the chart, linked in a hierarchy.
    This data-driven approach allows the organogram to be edited without changing
    the core Python code.
    """

    _name = "hr.organogram.node"
    _description = "Organogram Structure Node"
    _order = "sequence, id"

    name = fields.Char(string="Position/Unit Title", required=True)
    job_id = fields.Many2one(
        "hr.job",
        string="Related Job Position",
        help="Link this chart node to a specific job position. The system will find the employee holding this job.",
    )
    parent_id = fields.Many2one(
        "hr.organogram.node", string="Parent Unit", ondelete="cascade", index=True
    )
    child_ids = fields.One2many("hr.organogram.node", "parent_id", string="Child Units")
    sequence = fields.Integer(
        default=10, help="Used to order sibling nodes in the chart."
    )
    node_type = fields.Selection(
        [
            ("board", "Board Level"),
            ("ceo", "CEO"),
            ("c_level", "C-Level Executive"),
            ("director", "Director"),
            ("manager", "Manager/Head"),
            ("team", "Team/Division"),
            ("district", "District Office"),
        ],
        string="Node Type",
        default="manager",
        help="Helps in categorizing and styling nodes in the chart.",
    )

    is_district_head = fields.Boolean(
        string="Is District Head",
        help="If checked, branches under the 'Related District' will be loaded dynamically as children of this node.",
    )
    district_id = fields.Many2one(
        "hr.district",
        string="Related District",
        help="The district to load branches from, if 'Is District Head' is checked.",
    )
    division_id = fields.Many2one(
        "hr.division", string="Linked Division", copy=False, ondelete="set null"
    )

    @api.constrains("parent_id")
    def _check_hierarchy(self):
        if not self._check_recursion():
            raise models.ValidationError(
                "Error! You cannot create a recursive hierarchy."
            )

    def unlink(self):
        if self.env.context.get('no_sync'):
            return super().unlink()
            
        divisions_to_delete = self.mapped('division_id')
        res = super().unlink()
        divisions_to_delete.with_context(no_sync=True).unlink()
        return res