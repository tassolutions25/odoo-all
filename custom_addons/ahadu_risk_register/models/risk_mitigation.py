from datetime import date
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

import logging
_logger = logging.getLogger(__name__)

class RiskMitigation(models.Model):
    _name = 'risk.mitigation'
    _description = 'Risk Mitigation Action'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'timeline asc'
    _rec_name = 'action_plan'

    risk_id = fields.Many2one(
        'risk.register',
        string='Risk Entry',
        required=True,
        ondelete='cascade',
        help="The approved risk register entry this mitigation addresses.",
    )

    # Related fields for context from the risk form
    branch_id = fields.Many2one('hr.branch', related='risk_id.branch_id', store=True, string='Branch', readonly=True)
    department_id = fields.Many2one('hr.department', related='risk_id.department_id', store=True, string='Department', readonly=True)
    risk_event = fields.Text(related='risk_id.risk_event', string='Risk Event Description', readonly=True)
    inherent_risk_rating = fields.Selection(related='risk_id.inherent_risk_rating', string='Inherent Risk Rating', readonly=True)
    residual_risk_rating = fields.Selection(related='risk_id.residual_risk_rating', string='Residual Risk Rating', readonly=True)
    risk_maker_id = fields.Many2one('res.users', related='risk_id.risk_maker_id', string='Risk Maker', readonly=True)
    # Keep risk_owner_id as an alias for backward compatibility in views/reports
    risk_owner_id = fields.Many2one('res.users', related='risk_id.risk_maker_id', string='Risk Maker (Owner)', readonly=True)

    # Mitigation details
    action_plan = fields.Char(
        string='Action Plan',
        required=True,
        tracking=True,
        help="General name/summary of the mitigation action plan.",
    )
    detailed_action = fields.Text(
        string='Detailed Action / Checklist',
        required=True,
        tracking=True,
        help="Step-by-step detailed actions or checklist. Use standard lines or list items.",
    )
    timeline = fields.Date(
        string='Timeline (Target Date)',
        required=True,
        tracking=True,
        help="Target date for implementing this mitigation.",
    )
    action_executed = fields.Text(
        string='Action Executed',
        compute='_compute_action_executed',
        store=True,
        readonly=False,
        tracking=True,
        help="Details of actual action steps that have been taken (auto-computed from checklist items).",
    )
    time_actions_executed = fields.Date(
        string='Time Actions Were Executed',
        tracking=True,
        help="The date the action was actually executed.",
    )
    dependencies = fields.Text(
        string='Dependencies',
        help="Dependencies, blockers, or prerequisites for this action.",
    )

    checklist_item_ids = fields.One2many(
        'risk.mitigation.checklist.item',
        'mitigation_id',
        string='Detailed Checklist Items',
    )

    # Status tracking
    status = fields.Selection(
        selection=[
            ('not_attained', 'Not Attained'),
            ('partially_addressed', 'Partially Addressed'),
            ('fully_addressed', 'Fully Addressed'),
        ],
        string='Status (Attainment)',
        compute='_compute_status',
        store=True,
        tracking=True,
        help="Computed status matching Detailed Action items executed.",
    )
    progress_status = fields.Selection(
        selection=[
            ('open', 'Open'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
            ('overdue', 'Overdue'),
            ('escalated', 'Escalated'),
        ],
        string='Progress Status',
        default='open',
        required=True,
        tracking=True,
        help="General tracking state of the mitigation action.",
    )

    @api.depends('checklist_item_ids.is_checked')
    def _compute_action_executed(self):
        for rec in self:
            checked = rec.checklist_item_ids.filtered(lambda i: i.is_checked)
            if checked:
                rec.action_executed = '\n'.join([f"- {item.name}" for item in checked])
            else:
                rec.action_executed = ""

    @api.depends('checklist_item_ids.is_checked', 'detailed_action')
    def _compute_status(self):
        for rec in self:
            if not rec.checklist_item_ids:
                rec.status = 'not_attained'
            else:
                checked_count = len(rec.checklist_item_ids.filtered(lambda i: i.is_checked))
                total_count = len(rec.checklist_item_ids)
                if checked_count == total_count:
                    rec.status = 'fully_addressed'
                elif checked_count > 0:
                    rec.status = 'partially_addressed'
                else:
                    rec.status = 'not_attained'

    def _sync_checklist_items(self):
        for rec in self:
            if not rec.detailed_action:
                rec.checklist_item_ids.unlink()
                continue
            
            lines = [line.strip() for line in rec.detailed_action.split('\n') if line.strip()]
            clean_lines = []
            for line in lines:
                cleaned = line
                for prefix in ['- ', '* ', '[ ] ', '[x] ', '-', '*', '[ ]', '[x]']:
                    if cleaned.startswith(prefix):
                        cleaned = cleaned[len(prefix):].strip()
                if cleaned:
                    clean_lines.append(cleaned)
            
            existing_items = {item.name: item for item in rec.checklist_item_ids}
            keep_ids = []
            for name in clean_lines:
                if name in existing_items:
                    keep_ids.append(existing_items[name].id)
                else:
                    new_item = self.env['risk.mitigation.checklist.item'].create({
                        'mitigation_id': rec.id,
                        'name': name,
                        'is_checked': False,
                    })
                    keep_ids.append(new_item.id)
            
            to_delete = rec.checklist_item_ids.filtered(lambda i: i.id not in keep_ids)
            to_delete.unlink()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_checklist_items()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'detailed_action' in vals:
            self._sync_checklist_items()
        return res

    @api.constrains('risk_id')
    def _check_risk_approved(self):
        for rec in self:
            if rec.risk_id.state != 'approved':
                raise ValidationError(_(
                    "Mitigations can only be added to approved risks! "
                    "Current risk approval state is: %s"
                ) % rec.risk_id.state)

    # ── Scheduled Action: Overdue Detection & Escalation ────────────────

    @api.model
    def _cron_check_overdue_mitigations(self):
        """Daily scheduled action: detect overdue mitigations,
        update progress_status, notify risk owners, and log in Chatter."""
        today = date.today()
        overdue_mitigations = self.search([
            ('progress_status', 'not in', ['completed', 'overdue', 'escalated']),
            ('timeline', '<', today),
        ])

        _logger.info(
            "Cron: checking overdue mitigations — found %d records past deadline.",
            len(overdue_mitigations),
        )

        for mitigation in overdue_mitigations:
            # Mark as overdue
            mitigation.progress_status = 'overdue'

            # Build notification body
            risk = mitigation.risk_id
            body = _(
                "<p><strong>⚠️ Overdue Mitigation Alert</strong></p>"
                "<p>The following mitigation action is past its target date:</p>"
                "<ul>"
                "<li><strong>Action Plan:</strong> %(action_plan)s</li>"
                "<li><strong>Risk (RIN):</strong> %(rin)s</li>"
                "<li><strong>Target Date:</strong> %(timeline)s</li>"
                "<li><strong>Current Date:</strong> %(today)s</li>"
                "<li><strong>Days Overdue:</strong> %(days)s</li>"
                "</ul>"
                "<p>Please take immediate corrective action.</p>"
            ) % {
                'action_plan': mitigation.action_plan,
                'rin': risk.name or '',
                'timeline': str(mitigation.timeline),
                'today': str(today),
                'days': (today - mitigation.timeline).days,
            }

            # Post to the mitigation's own Chatter
            mitigation.message_post(
                body=body,
                subject=_("⚠️ Overdue: %s") % mitigation.action_plan,
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )

            # Also post to the parent risk's Chatter
            risk.message_post(
                body=body,
                subject=_("⚠️ Overdue Mitigation: %s") % mitigation.action_plan,
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )

            # Send emails directly via mail.mail to force email delivery
            partners_to_notify = []
            if risk.risk_owner_id and risk.risk_owner_id.partner_id:
                partners_to_notify.append(risk.risk_owner_id.partner_id.id)
                # Try to find owner's manager via employee link
                owner_employee = risk.risk_owner_id.employee_id or (
                    risk.risk_owner_id.employee_ids[0] if risk.risk_owner_id.employee_ids else None
                )
                if owner_employee and owner_employee.parent_id and owner_employee.parent_id.user_id:
                    manager_partner = owner_employee.parent_id.user_id.partner_id
                    if manager_partner:
                        partners_to_notify.append(manager_partner.id)

            for partner_id in partners_to_notify:
                partner = self.env['res.partner'].browse(partner_id)
                if partner.email:
                    mail_values = {
                        'subject': _("⚠️ Overdue Mitigation: %s") % mitigation.action_plan,
                        'body_html': body,
                        'email_to': partner.email,
                        'email_from': self.env.user.email or self.env.company.email or 'risk-register@ahadubank.com',
                    }
                    try:
                        mail = self.env['mail.mail'].sudo().create(mail_values)
                        mail.send()
                    except Exception as e:
                        _logger.error("Failed to send overdue email to %s: %s", partner.email, e)

        _logger.info("Cron: overdue mitigation check complete. %d records escalated.", len(overdue_mitigations))
        return True


class RiskMitigationChecklistItem(models.Model):
    _name = 'risk.mitigation.checklist.item'
    _description = 'Mitigation Checklist Item'
    _order = 'id asc'

    mitigation_id = fields.Many2one('risk.mitigation', string='Mitigation', ondelete='cascade')
    name = fields.Char(string='Action Item', required=True)
    is_checked = fields.Boolean(string='Executed?', default=False)


