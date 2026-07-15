from datetime import date
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

# ── Rating classification helpers ────────────────────────────────────────
RISK_RATING_THRESHOLDS = [
    (2, 'very_low'),
    (6, 'low'),
    (12, 'medium'),
    (20, 'high'),
    (25, 'very_high'),
]

CONTROL_RATING_THRESHOLDS = [
    (2, 'very_weak'),
    (6, 'weak'),
    (12, 'moderate'),
    (20, 'strong'),
    (25, 'very_strong'),
]

# BRD Residual Risk matrix (Inherent ↓ × Control →)
# Keys: (inherent_rating, control_rating) → residual_rating
RESIDUAL_MATRIX = {
    ('very_high', 'very_weak'): 'very_high',
    ('very_high', 'weak'): 'high',
    ('very_high', 'moderate'): 'medium',
    ('very_high', 'strong'): 'medium',
    ('very_high', 'very_strong'): 'low',
    ('high', 'very_weak'): 'high',
    ('high', 'weak'): 'high',
    ('high', 'moderate'): 'medium',
    ('high', 'strong'): 'low',
    ('high', 'very_strong'): 'low',
    ('medium', 'very_weak'): 'medium',
    ('medium', 'weak'): 'medium',
    ('medium', 'moderate'): 'low',
    ('medium', 'strong'): 'low',
    ('medium', 'very_strong'): 'very_low',
    ('low', 'very_weak'): 'low',
    ('low', 'weak'): 'low',
    ('low', 'moderate'): 'low',
    ('low', 'strong'): 'very_low',
    ('low', 'very_strong'): 'very_low',
    ('very_low', 'very_weak'): 'very_low',
    ('very_low', 'weak'): 'very_low',
    ('very_low', 'moderate'): 'very_low',
    ('very_low', 'strong'): 'very_low',
    ('very_low', 'very_strong'): 'very_low',
}


def _classify_risk(score):
    """Classify a risk score (0-25) into a rating label."""
    for threshold, label in RISK_RATING_THRESHOLDS:
        if score <= threshold:
            return label
    return 'very_high'


def _classify_control(score):
    """Classify a control strength score (0-25) into a rating label."""
    for threshold, label in CONTROL_RATING_THRESHOLDS:
        if score <= threshold:
            return label
    return 'very_strong'


class RiskRegister(models.Model):
    _name = 'risk.register'
    _description = 'Risk Register Entry'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    _rec_name = 'name'

    # ── Identification ───────────────────────────────────────────────────
    name = fields.Char(
        string='RIN',
        readonly=True,
        copy=False,
        default=lambda self: _('New'),
        help="Risk Identification Number — auto-generated on creation.",
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        help="The company / legal entity managing this risk.",
    )
    is_rcmd_or_board = fields.Boolean(
        string='Is RCMD or Board Member',
        compute='_compute_is_rcmd_or_board',
        help="Technical field to dynamically control field readability based on user group.",
    )
    @api.model
    def _default_branch_id(self):
        employee = self.env.user.employee_id or (self.env.user.employee_ids[0] if self.env.user.employee_ids else False)
        return employee.branch_id.id if employee and employee.branch_id else False

    @api.model
    def _default_department_id(self):
        employee = self.env.user.employee_id or (self.env.user.employee_ids[0] if self.env.user.employee_ids else False)
        return employee.department_id.id if employee and employee.department_id else False

    branch_id = fields.Many2one(
        'hr.branch',
        string='Branch',
        required=True,
        tracking=True,
        default=lambda self: self._default_branch_id(),
        help="The branch / business unit where this risk was identified.",
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        required=True,
        tracking=True,
        default=lambda self: self._default_department_id(),
        help="The department responsible for managing this risk.",
    )
    business_objective = fields.Char(
        string='Business Objectives',
        help="The strategic or operational objective affected by this risk.",
    )
    business_process = fields.Char(
        string='Business Processes',
        help="The business process or risk area related to this risk event.",
    )
    risk_event = fields.Text(
        string='Risk Event',
        required=True,
        tracking=True,
        help="Description of the risk event — what could go wrong.",
    )
    risk_category_id = fields.Many2one(
        'risk.category',
        string='Risk Category',
        required=True,
        tracking=True,
        help="Select the risk category per the bank's risk taxonomy.",
    )
    root_cause = fields.Text(
        string='Root Cause',
        help="Underlying root cause(s) of the risk event.",
    )
    date_occurred = fields.Date(
        string='Date Occurred',
        help="The date the risk event actually occurred (if applicable).",
    )
    date_identified = fields.Date(
        string='Date Identified',
        default=fields.Date.context_today,
        help="The date the risk was formally identified and registered.",
    )

    # ── Inherent Risk Assessment ─────────────────────────────────────────
    likelihood = fields.Selection(
        selection=[
            ('1', '1 — Rare'),
            ('2', '2 — Unlikely'),
            ('3', '3 — Possible'),
            ('4', '4 — Likely'),
            ('5', '5 — Almost Certain'),
        ],
        string='Likelihood',
        required=True,
        tracking=True,
        help="Probability of the risk event occurring (1=Rare … 5=Almost Certain).",
    )
    impact = fields.Selection(
        selection=[
            ('1', '1 — Insignificant'),
            ('2', '2 — Minor'),
            ('3', '3 — Moderate'),
            ('4', '4 — Major'),
            ('5', '5 — Critical'),
        ],
        string='Impact',
        required=True,
        tracking=True,
        help="Severity of the impact if the risk materialises (1=Insignificant … 5=Critical).",
    )
    inherent_risk_score = fields.Integer(
        string='Inherent Risk Score',
        compute='_compute_inherent_risk',
        store=True,
        help="Likelihood × Impact (range 1–25).",
    )
    inherent_risk_rating = fields.Selection(
        selection=[
            ('very_low', 'Very Low'),
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('very_high', 'Very High'),
        ],
        string='Inherent Risk Rating',
        compute='_compute_inherent_risk',
        store=True,
        help="Classification: Very Low (≤2), Low (3-6), Medium (7-12), High (13-20), Very High (>20).",
    )

    # ── Controls & Mitigation ────────────────────────────────────────────
    existing_controls = fields.Text(
        string='Existing Mitigation / Controls',
        help="Describe the current controls and mitigation measures in place.",
    )
    control_adequacy = fields.Selection(
        selection=[
            ('1', 'Weak (1)'),
            ('2', 'Deficient (2)'),
            ('3', 'Marginal (3)'),
            ('4', 'Acceptable (4)'),
            ('5', 'Strong (5)'),
        ],
        string='Control Adequacy',
        required=True,
        tracking=True,
        help="How adequate are the existing controls? (1=Weak … 5=Strong).",
    )
    control_effectiveness = fields.Selection(
        selection=[
            ('1', 'Weak (1)'),
            ('2', 'Deficient (2)'),
            ('3', 'Marginal (3)'),
            ('4', 'Acceptable (4)'),
            ('5', 'Strong (5)'),
        ],
        string='Control Effectiveness',
        required=True,
        tracking=True,
        help="How effective are the existing controls? (1=Weak … 5=Strong).",
    )
    control_strength_score = fields.Integer(
        string='Control Strength Score',
        compute='_compute_control_strength',
        store=True,
        help="Adequacy × Effectiveness (range 1–25).",
    )

    # ── Exact color maps from the Excel reference sheets ─────────────────

    # Inherent Risk: 5×5 cell colors from "Rating Matrix" sheet
    INHERENT_CELL_COLORS = {
        (1, 1): '#00B050', (1, 2): '#00B050', (1, 3): '#92D050', (1, 4): '#92D050', (1, 5): '#92D050',
        (2, 1): '#00B050', (2, 2): '#92D050', (2, 3): '#92D050', (2, 4): '#FFFF00', (2, 5): '#FFFF00',
        (3, 1): '#92D050', (3, 2): '#92D050', (3, 3): '#FFFF00', (3, 4): '#FFFF00', (3, 5): '#FF0000',
        (4, 1): '#92D050', (4, 2): '#FFFF00', (4, 3): '#FFFF00', (4, 4): '#FF0000', (4, 5): '#FF0000',
        (5, 1): '#92D050', (5, 2): '#FFFF00', (5, 3): '#FF0000', (5, 4): '#FF0000', (5, 5): '#A50021',
    }
    # Fallback by rating label
    INHERENT_RATING_COLORS = {
        'very_high': '#A50021', 'high': '#FF0000', 'medium': '#FFFF00',
        'low': '#92D050', 'very_low': '#00B050',
    }

    # Parameter level colors
    LIKELIHOOD_COLORS = {
        1: '#109F10', 2: '#AFCE0F', 3: '#FFD00B', 4: '#E66E00', 5: '#DF0A0A',
    }
    IMPACT_COLORS = {
        1: '#109F10', 2: '#AFCE0F', 3: '#FFD00B', 4: '#E66E00', 5: '#FF0000',
    }
    ADEQUACY_COLORS = {
        1: '#C00000', 2: '#FF0000', 3: '#FFFF00', 4: '#92D050', 5: '#00B050',
    }
    EFFECTIVENESS_COLORS = {
        1: '#C00000', 2: '#FF0000', 3: '#FFFF00', 4: '#B6DDE8', 5: '#00B050',
    }

    # Control Strength: 5×5 cell colors from "Control Matrix" sheet
    CONTROL_CELL_COLORS = {
        (1, 1): '#C00000', (1, 2): '#C00000', (1, 3): '#FF4B21', (1, 4): '#FF4B21', (1, 5): '#FF4B21',
        (2, 1): '#C00000', (2, 2): '#FF4B21', (2, 3): '#FF4B21', (2, 4): '#FFFF00', (2, 5): '#FFFF00',
        (3, 1): '#FF4B21', (3, 2): '#FF4B21', (3, 3): '#FFFF00', (3, 4): '#FFFF00', (3, 5): '#99FF33',
        (4, 1): '#FF4B21', (4, 2): '#FFFF00', (4, 3): '#FFFF00', (4, 4): '#99FF33', (4, 5): '#99FF33',
        (5, 1): '#FF4B21', (5, 2): '#FFFF00', (5, 3): '#99FF33', (5, 4): '#99FF33', (5, 5): '#009900',
    }
    CONTROL_RATING_COLORS = {
        'very_strong': '#009900', 'strong': '#99FF33', 'moderate': '#FFFF00',
        'weak': '#FF4B21', 'very_weak': '#C00000',
    }

    # Residual Risk: cell colors from "RESIDUAL LEVEL" sheet
    RESIDUAL_CELL_COLORS = {
        ('very_high', 'very_weak'): '#B40000', ('very_high', 'weak'): '#FF0000',
        ('very_high', 'moderate'): '#FFFF00', ('very_high', 'strong'): '#FFFF00',
        ('very_high', 'very_strong'): '#92D050',
        ('high', 'very_weak'): '#FF0000', ('high', 'weak'): '#FF0000',
        ('high', 'moderate'): '#FFFF00', ('high', 'strong'): '#92D050',
        ('high', 'very_strong'): '#92D050',
        ('medium', 'very_weak'): '#FFFF00', ('medium', 'weak'): '#FFFF00',
        ('medium', 'moderate'): '#92D050', ('medium', 'strong'): '#92D050',
        ('medium', 'very_strong'): '#525252',
        ('low', 'very_weak'): '#92D050', ('low', 'weak'): '#92D050',
        ('low', 'moderate'): '#92D050', ('low', 'strong'): '#525252',
        ('low', 'very_strong'): '#525252',
        ('very_low', 'very_weak'): '#525252', ('very_low', 'weak'): '#525252',
        ('very_low', 'moderate'): '#525252', ('very_low', 'strong'): '#525252',
        ('very_low', 'very_strong'): '#525252',
    }
    RESIDUAL_RATING_COLORS = {
        'very_high': '#B40000', 'high': '#FF0000', 'medium': '#FFFF00',
        'low': '#92D050', 'very_low': '#525252',
    }

    def get_rating_color(self, field_name):
        """Return the exact background color matching the company Excel sheets."""
        self.ensure_one()
        if field_name == 'likelihood':
            val = int(self.likelihood) if self.likelihood else None
            return self.LIKELIHOOD_COLORS.get(val, '#FFFFFF') if val else '#FFFFFF'
        elif field_name == 'impact':
            val = int(self.impact) if self.impact else None
            return self.IMPACT_COLORS.get(val, '#FFFFFF') if val else '#FFFFFF'
        elif field_name == 'adequacy':
            val = int(self.control_adequacy) if self.control_adequacy else None
            return self.ADEQUACY_COLORS.get(val, '#FFFFFF') if val else '#FFFFFF'
        elif field_name == 'effectiveness':
            val = int(self.control_effectiveness) if self.control_effectiveness else None
            return self.EFFECTIVENESS_COLORS.get(val, '#FFFFFF') if val else '#FFFFFF'
        elif field_name == 'inherent':
            # Try cell-specific color first
            if self.likelihood and self.impact:
                key = (int(self.likelihood), int(self.impact))
                color = self.INHERENT_CELL_COLORS.get(key)
                if color:
                    return color
            return self.INHERENT_RATING_COLORS.get(self.inherent_risk_rating, '#CCCCCC')
        elif field_name == 'control':
            if self.control_adequacy and self.control_effectiveness:
                key = (int(self.control_adequacy), int(self.control_effectiveness))
                color = self.CONTROL_CELL_COLORS.get(key)
                if color:
                    return color
            return self.CONTROL_RATING_COLORS.get(self.control_strength_rating, '#CCCCCC')
        elif field_name == 'residual':
            if self.inherent_risk_rating and self.control_strength_rating:
                key = (self.inherent_risk_rating, self.control_strength_rating)
                color = self.RESIDUAL_CELL_COLORS.get(key)
                if color:
                    return color
            return self.RESIDUAL_RATING_COLORS.get(self.residual_risk_rating, '#CCCCCC')
        return '#CCCCCC'

    def get_rating_text_color(self, field_name):
        """Return white text for dark backgrounds, black for light."""
        bg = self.get_rating_color(field_name)
        dark_bgs = ('#990033', '#FF0000', '#C00000', '#109F10', '#00B050', '#1B4170', '#A50021', '#B40000', '#009900', '#DF0A0A', '#525252')
        if bg in dark_bgs:
            return '#FFFFFF'
        return '#000000'

    def get_fiscal_year_label(self):
        """Return the Ethiopian fiscal year label based on the current date.
        Ethiopian FY runs July 8 to July 7 (Hamle 1 to Sene 30).
        """
        today = date.today()
        if today.month > 7 or (today.month == 7 and today.day >= 8):
            fy_start = today.year
            fy_end = today.year + 1
        else:
            fy_start = today.year - 1
            fy_end = today.year
        return f"FY {fy_start}/{str(fy_end)[-2:]}"

    control_strength_rating = fields.Selection(
        selection=[
            ('very_weak', 'Very Weak'),
            ('weak', 'Weak'),
            ('moderate', 'Moderate'),
            ('strong', 'Strong'),
            ('very_strong', 'Very Strong'),
        ],
        string='Control Strength Rating',
        compute='_compute_control_strength',
        store=True,
        help="Classification: Very Weak (≤2), Weak (3-6), Moderate (7-12), Strong (13-20), Very Strong (>20).",
    )

    # ── Residual Risk ────────────────────────────────────────────────────
    residual_risk_score = fields.Float(
        string='Residual Risk Score',
        compute='_compute_residual_risk',
        store=True,
        digits=(5, 2),
        help="Inherent Risk Score × (1 − Control Strength / 25).",
    )
    residual_risk_rating = fields.Selection(
        selection=[
            ('very_low', 'Very Low'),
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('very_high', 'Very High'),
        ],
        string='Residual Risk Rating',
        compute='_compute_residual_risk',
        store=True,
        help="Derived from the BRD Residual Risk Matrix (Inherent Rating × Control Rating).",
    )

    # ── Additional fields ────────────────────────────────────────────────
    additional_mitigation = fields.Text(
        string='Additional Mitigation Actions',
        help="Planned additional controls or mitigation beyond existing measures.",
    )
    key_risk_indicator = fields.Text(
        string='Key Risk Indicator (KRI)',
        help="Metrics or indicators used to monitor this risk.",
    )
    risk_maker_id = fields.Many2one(
        'res.users',
        string='Risk Maker',
        default=lambda self: self.env.user,
        tracking=True,
        help="The user who registered/created this risk entry.",
    )
    # Stored related field for backward compatibility with existing noupdate="1" record rules in database
    risk_owner_id = fields.Many2one(
        'res.users',
        related='risk_maker_id',
        string='Risk Owner (User)',
        store=True,
        readonly=True,
    )
    risk_owner_ids = fields.Many2many(
        'hr.department',
        'risk_register_dept_rel',
        'risk_id',
        'dept_id',
        string='Risk Owner (Departments)',
        tracking=True,
        help="The department(s) responsible for managing this risk. Defaults to the registering department.",
    )
    checker_id = fields.Many2one(
        'res.users',
        string='Risk Checker',
        compute='_compute_checker_id',
        store=True,
        help="The direct manager of the Risk Maker (auto-computed from HR hierarchy).",
    )
    reference_document = fields.Binary(
        string='Risk Registration Reference',
        attachment=True,
        help="Upload reference documents related to this risk (PDF, DOCX, XLSX, images, etc.).",
    )
    reference_document_filename = fields.Char(
        string='Reference Filename',
    )

    @api.depends('risk_maker_id')
    def _compute_checker_id(self):
        for rec in self:
            checker = False
            if rec.risk_maker_id:
                emp = rec.risk_maker_id.employee_id or (
                    rec.risk_maker_id.employee_ids[0] if rec.risk_maker_id.employee_ids else False
                )
                if emp and emp.parent_id and emp.parent_id.user_id:
                    checker = emp.parent_id.user_id.id
            rec.checker_id = checker
    status = fields.Selection(
        selection=[
            ('open', 'Open'),
            ('in_progress', 'In Progress'),
            ('closed', 'Closed'),
            ('overdue', 'Overdue'),
        ],
        string='Status',
        default='open',
        required=True,
        tracking=True,
        help="Current lifecycle status of this risk entry.",
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('waiting_leader', 'Waiting Leader (Checker)'),
            ('waiting_rcmd', 'Waiting RCMD (Approver)'),
            ('approved', 'Approved'),
        ],
        string='Approval State',
        default='draft',
        required=True,
        tracking=True,
        help="Maker-Checker approval lifecycle state of this risk.",
    )
    mitigation_ids = fields.One2many(
        'risk.mitigation',
        'risk_id',
        string='Mitigations',
    )
    mitigation_count = fields.Integer(
        string='Mitigation Controls Count',
        compute='_compute_mitigation_count',
        help="Number of mitigation actions associated with this risk.",
    )

    @api.depends('mitigation_ids')
    def _compute_mitigation_count(self):
        for rec in self:
            rec.mitigation_count = len(rec.mitigation_ids)

    def action_view_mitigations(self):
        self.ensure_one()
        return {
            'name': _('Mitigation Controls'),
            'type': 'ir.actions.act_window',
            'res_model': 'risk.mitigation',
            'view_mode': 'list,form,kanban',
            'domain': [('risk_id', '=', self.id)],
            'context': {'default_risk_id': self.id},
            'target': 'current',
        }

    # ── Computed Methods ─────────────────────────────────────────────────

    @api.depends_context('uid')
    def _compute_is_rcmd_or_board(self):
        has_group = self.env.user.has_group('ahadu_risk_register.group_rcmd_admin') or \
                    self.env.user.has_group('ahadu_risk_register.group_board_committee')
        for rec in self:
            rec.is_rcmd_or_board = has_group

    @api.depends('likelihood', 'impact')
    def _compute_inherent_risk(self):
        for rec in self:
            if rec.likelihood and rec.impact:
                score = int(rec.likelihood) * int(rec.impact)
                rec.inherent_risk_score = score
                rec.inherent_risk_rating = _classify_risk(score)
            else:
                rec.inherent_risk_score = 0
                rec.inherent_risk_rating = False

    @api.depends('control_adequacy', 'control_effectiveness')
    def _compute_control_strength(self):
        for rec in self:
            if rec.control_adequacy and rec.control_effectiveness:
                score = int(rec.control_adequacy) * int(rec.control_effectiveness)
                rec.control_strength_score = score
                rec.control_strength_rating = _classify_control(score)
            else:
                rec.control_strength_score = 0
                rec.control_strength_rating = False

    @api.depends('inherent_risk_score', 'inherent_risk_rating',
                 'control_strength_score', 'control_strength_rating')
    def _compute_residual_risk(self):
        for rec in self:
            if rec.inherent_risk_score and rec.control_strength_score:
                # BRD formula: Residual = Inherent × (1 − Control / 25)
                score = rec.inherent_risk_score * (1 - rec.control_strength_score / 25.0)
                rec.residual_risk_score = round(score, 2)
                # Matrix lookup
                key = (rec.inherent_risk_rating, rec.control_strength_rating)
                rec.residual_risk_rating = RESIDUAL_MATRIX.get(key, 'medium')
            else:
                rec.residual_risk_score = 0.0
                rec.residual_risk_rating = False

    # ── CRUD Overrides ───────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        is_admin_or_board = self.env.user.has_group('ahadu_risk_register.group_rcmd_admin') or \
                            self.env.user.has_group('ahadu_risk_register.group_board_committee')
        for vals in vals_list:
            employee = self.env.user.employee_id or (self.env.user.employee_ids[0] if self.env.user.employee_ids else False)
            if not is_admin_or_board:
                if employee:
                    if employee.branch_id:
                        vals['branch_id'] = employee.branch_id.id
                    if employee.department_id:
                        vals['department_id'] = employee.department_id.id

            # Auto-populate risk_owner_ids with the registering department if not set
            if not vals.get('risk_owner_ids') and employee and employee.department_id:
                vals['risk_owner_ids'] = [(4, employee.department_id.id)]

            if vals.get('name', _('New')) == _('New'):
                # Build RIN: {branch_code}{seq_padded_2}
                branch_code = ''
                if vals.get('branch_id'):
                    branch = self.env['hr.branch'].browse(vals['branch_id'])
                    branch_code = branch.code or ''
                seq = self.env['ir.sequence'].next_by_code('risk.register') or '00'
                vals['name'] = '{}{}'.format(branch_code, seq)
        return super().create(vals_list)

    def write(self, vals):
        is_admin_or_board = self.env.user.has_group('ahadu_risk_register.group_rcmd_admin') or \
                            self.env.user.has_group('ahadu_risk_register.group_board_committee')
        if not is_admin_or_board:
            # Enforce branch_id and department_id cannot be changed
            if 'branch_id' in vals or 'department_id' in vals:
                employee = self.env.user.employee_id or (self.env.user.employee_ids[0] if self.env.user.employee_ids else False)
                if employee:
                    if 'branch_id' in vals and employee.branch_id and vals['branch_id'] != employee.branch_id.id:
                        raise ValidationError(_("You cannot change the branch field."))
                    if 'department_id' in vals and employee.department_id and vals['department_id'] != employee.department_id.id:
                        raise ValidationError(_("You cannot change the department field."))

            # If changing fields other than state or status or Chatter ones, ensure state is draft
            non_wf_fields = [f for f in vals.keys() if f not in ('state', 'status', 'message_attachment_count')]
            if non_wf_fields:
                for rec in self:
                    if rec.state != 'draft':
                        raise ValidationError(_("You can only edit risk entries when they are in Draft state."))
        return super(RiskRegister, self).write(vals)

    def action_open(self):
        self.write({'status': 'open'})

    def action_in_progress(self):
        self.write({'status': 'in_progress'})

    def action_close(self):
        self.write({'status': 'closed'})

    def action_overdue(self):
        self.write({'status': 'overdue'})

    def _get_employee_and_job(self):
        self.ensure_one()
        user = self.env.user
        employee = user.employee_id
        if not employee:
            employee = user.employee_ids[0] if user.employee_ids else None
        job_name = employee.job_id.name or '' if employee and employee.job_id else ''
        return employee, job_name.lower()

    def _send_workflow_email(self, partner_ids, subject, body):
        """Send direct email to partners to force email delivery bypassing Odoo internal settings."""
        for partner in self.env['res.partner'].sudo().browse(partner_ids):
            if partner.email:
                mail_values = {
                    'subject': subject,
                    'body_html': body,
                    'email_to': partner.email,
                    'email_from': self.env.user.email or self.env.company.email or 'risk-register@ahadubank.com',
                }
                try:
                    mail = self.env['mail.mail'].sudo().create(mail_values)
                    mail.send()
                except Exception:
                    pass

    def action_submit_to_leader(self):
        for rec in self:
            if rec.state != 'draft':
                raise ValidationError(_("Only draft risks can be submitted for review."))
            
            # Check Maker roles: Enforce that the user has a linked employee and a direct manager
            if not self.env.user.has_group('ahadu_risk_register.group_rcmd_admin') and not self.env.user.has_group('ahadu_risk_register.group_board_committee'):
                employee, job_name = rec._get_employee_and_job()
                if not employee:
                    raise ValidationError(_("You must have a linked employee record to submit risks."))
                if not employee.parent_id:
                    raise ValidationError(_("You must have a direct manager configured in your Employee profile to submit a risk. Please contact HR."))

            rec.state = 'waiting_leader'
            rec.message_post(body=_("Risk submitted to direct manager/leader for review."))

            # Send email to the Checker (direct manager of Risk Maker)
            maker_user = rec.risk_maker_id or rec.create_uid
            maker_employee = maker_user.employee_id or (maker_user.employee_ids[0] if maker_user.employee_ids else None)
            if maker_employee and maker_employee.parent_id and maker_employee.parent_id.user_id:
                manager_partner = maker_employee.parent_id.user_id.partner_id
                if manager_partner:
                    subject = _("Risk Register: Verification Required (RIN: %s)") % rec.name
                    body = _(
                        "<p>Dear Manager,</p>"
                        "<p>A new risk entry has been submitted by <strong>%s</strong> and requires your verification:</p>"
                        "<ul>"
                        "<li><strong>RIN:</strong> %s</li>"
                        "<li><strong>Risk Event:</strong> %s</li>"
                        "<li><strong>Branch:</strong> %s</li>"
                        "<li><strong>Department:</strong> %s</li>"
                        "</ul>"
                        "<p>Please log in to Odoo to verify and submit this risk.</p>"
                    ) % (maker_employee.name, rec.name or '', rec.risk_event or '', rec.branch_id.name or '', rec.department_id.name or '')
                    rec._send_workflow_email([manager_partner.id], subject, body)

    def action_submit_to_rcmd(self):
        for rec in self:
            if rec.state != 'waiting_leader':
                raise ValidationError(_("Only risks waiting for leader approval can be verified."))
            
            # Group permissions check
            if not self.env.user.has_group('ahadu_risk_register.group_risk_checker') and \
               not self.env.user.has_group('ahadu_risk_register.group_rcmd_admin') and \
               not self.env.user.has_group('ahadu_risk_register.group_board_committee'):
                raise ValidationError(_("Only Risk Checkers (Branch Managers) or RCMD/Board members can verify risks."))
            
            # Direct manager check for non-RCMD/Board
            if not self.env.user.has_group('ahadu_risk_register.group_rcmd_admin') and not self.env.user.has_group('ahadu_risk_register.group_board_committee'):
                employee, job_name = rec._get_employee_and_job()
                if not employee:
                    raise ValidationError(_("You must have a linked employee record to verify risks."))
                
                # Retrieve the employee of the maker
                maker_user = rec.risk_maker_id or rec.create_uid
                maker_employee = maker_user.employee_id or (maker_user.employee_ids[0] if maker_user.employee_ids else None)
                if not maker_employee:
                    fallback_user = rec.create_uid
                    maker_employee = fallback_user.employee_id or (fallback_user.employee_ids[0] if fallback_user.employee_ids else None)
                
                if not maker_employee or not maker_employee.parent_id:
                    raise ValidationError(_("The creator/owner has no direct manager defined. Please assign a parent manager in HR."))
                
                if employee.id != maker_employee.parent_id.id:
                    raise ValidationError(_("Only the direct manager (%s) can verify this risk.") % maker_employee.parent_id.name)

            rec.state = 'waiting_rcmd'
            rec.message_post(body=_("Risk verified by direct manager and submitted to RCMD/Board for approval."))

            # Send email to RCMD admins and Board committee
            rcmd_group = self.env.ref('ahadu_risk_register.group_rcmd_admin')
            board_group = self.env.ref('ahadu_risk_register.group_board_committee')
            users = rcmd_group.users | board_group.users
            partner_ids = users.mapped('partner_id').ids
            if partner_ids:
                subject = _("Risk Register: Approval Required (RIN: %s)") % rec.name
                body = _(
                    "<p>Dear RCMD / Board Member,</p>"
                    "<p>A risk entry has been verified by the direct manager and requires your approval:</p>"
                    "<ul>"
                    "<li><strong>RIN:</strong> %s</li>"
                    "<li><strong>Risk Event:</strong> %s</li>"
                    "<li><strong>Branch:</strong> %s</li>"
                    "<li><strong>Department:</strong> %s</li>"
                    "</ul>"
                    "<p>Please log in to Odoo to review and approve/reject this risk.</p>"
                ) % (rec.name or '', rec.risk_event or '', rec.branch_id.name or '', rec.department_id.name or '')
                rec._send_workflow_email(partner_ids, subject, body)

    def action_approve(self):
        for rec in self:
            if rec.state != 'waiting_rcmd':
                raise ValidationError(_("Only risks waiting for RCMD/Board approval can be approved."))
            
            if not self.env.user.has_group('ahadu_risk_register.group_rcmd_admin') and not self.env.user.has_group('ahadu_risk_register.group_board_committee'):
                raise ValidationError(_("Only RCMD Administrators or Board Committee members can approve risks."))
                
            rec.state = 'approved'
            rec.message_post(body=_("Risk officially approved by RCMD/Board."))

            # Send email to Risk Maker
            maker_partner = rec.risk_maker_id.partner_id
            if maker_partner:
                subject = _("Risk Register: Risk Approved (RIN: %s)") % rec.name
                body = _(
                    "<p>Dear Risk Maker,</p>"
                    "<p>Your risk register entry has been officially approved by RCMD/Board:</p>"
                    "<ul>"
                    "<li><strong>RIN:</strong> %s</li>"
                    "<li><strong>Risk Event:</strong> %s</li>"
                    "<li><strong>Residual Risk:</strong> %s</li>"
                    "</ul>"
                    "<p>Thank you.</p>"
                ) % (rec.name or '', rec.risk_event or '', rec.residual_risk_rating or '')
                rec._send_workflow_email([maker_partner.id], subject, body)

    def action_reject(self, reason=''):
        for rec in self:
            if rec.state not in ('waiting_leader', 'waiting_rcmd'):
                raise ValidationError(_("Only pending risks can be rejected."))
            
            # Check permissions based on state
            if rec.state == 'waiting_leader':
                if not self.env.user.has_group('ahadu_risk_register.group_risk_checker') and \
                   not self.env.user.has_group('ahadu_risk_register.group_rcmd_admin') and \
                   not self.env.user.has_group('ahadu_risk_register.group_board_committee'):
                    raise ValidationError(_("Only Risk Checkers (Branch Managers) or RCMD/Board members can reject at this stage."))
            elif rec.state == 'waiting_rcmd':
                if not self.env.user.has_group('ahadu_risk_register.group_rcmd_admin') and \
                   not self.env.user.has_group('ahadu_risk_register.group_board_committee'):
                    raise ValidationError(_("Only RCMD Administrators or Board Committee members can reject at this stage."))
            
            rec.state = 'draft'
            rec.message_post(body=_("Risk rejected and reset to Draft. Reason: %s") % (reason or _("No reason provided.")))

            # Send email to Risk Maker
            maker_partner = rec.risk_maker_id.partner_id
            if maker_partner:
                subject = _("Risk Register: Risk Rejected (RIN: %s)") % rec.name
                body = _(
                    "<p>Dear Risk Maker,</p>"
                    "<p>Your risk register entry has been rejected and reset to Draft:</p>"
                    "<ul>"
                    "<li><strong>RIN:</strong> %s</li>"
                    "<li><strong>Risk Event:</strong> %s</li>"
                    "<li><strong>Rejection Reason:</strong> %s</li>"
                    "</ul>"
                    "<p>Please make the necessary changes and submit again.</p>"
                ) % (rec.name or '', rec.risk_event or '', reason or _("No reason provided."))
                rec._send_workflow_email([maker_partner.id], subject, body)
