import io
import os
import base64
from datetime import date

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.modules import get_module_resource

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None


# ── Label maps for human-readable export ─────────────────────────────────
RISK_CATEGORY_LABELS = {
    'credit': 'Credit Risk',
    'liquidity': 'Liquidity Risk',
    'market': 'Market Risk',
    'reputational': 'Reputational Risk',
    'compliance': 'Compliance Risk',
    'operational': 'Operational Risk',
    'it_cyber': 'IT / Cyber Risk',
    'strategic': 'Strategic Risk',
    'emerging': 'Emerging Risk',
}

RATING_LABELS = {
    'very_low': 'Very Low',
    'low': 'Low',
    'medium': 'Medium',
    'high': 'High',
    'very_high': 'Very High',
}

CONTROL_LABELS = {
    'very_weak': 'Very Weak',
    'weak': 'Weak',
    'moderate': 'Moderate',
    'strong': 'Strong',
    'very_strong': 'Very Strong',
}

STATUS_LABELS = {
    'open': 'Open',
    'in_progress': 'In Progress',
    'closed': 'Closed',
    'overdue': 'Overdue',
}

# ── Parameter Display Maps ───────────────────────────────────────────────
LIKELIHOOD_EXCEL_MAP = {
    '1': 'Rare (1)',
    '2': 'Unlikely (2)',
    '3': 'Possible (3)',
    '4': 'Likely (4)',
    '5': 'Almost Certain (5)',
}

IMPACT_EXCEL_MAP = {
    '1': 'Insignificant (1)',
    '2': 'Minor (2)',
    '3': 'Moderate (3)',
    '4': 'Major (4)',
    '5': 'Critical (5)',
}

ADEQUACY_EXCEL_MAP = {
    '1': 'Weak (1)',
    '2': 'Deficient (2)',
    '3': 'Marginal (3)',
    '4': 'Acceptable (4)',
    '5': 'Strong (5)',
}

EFFECTIVENESS_EXCEL_MAP = {
    '1': 'Weak (1)',
    '2': 'Deficient (2)',
    '3': 'Marginal (3)',
    '4': 'Acceptable (4)',
    '5': 'Strong (5)',
}

# ── Exact Inherent Risk 5×5 Rating Matrix Colors ────────────────────────
INHERENT_RISK_CELL_COLORS = {
    (1, 1): '#00B050', (1, 2): '#00B050', (1, 3): '#92D050', (1, 4): '#92D050', (1, 5): '#92D050',
    (2, 1): '#00B050', (2, 2): '#92D050', (2, 3): '#92D050', (2, 4): '#FFFF00', (2, 5): '#FFFF00',
    (3, 1): '#92D050', (3, 2): '#92D050', (3, 3): '#FFFF00', (3, 4): '#FFFF00', (3, 5): '#FF0000',
    (4, 1): '#92D050', (4, 2): '#FFFF00', (4, 3): '#FFFF00', (4, 4): '#FF0000', (4, 5): '#FF0000',
    (5, 1): '#92D050', (5, 2): '#FFFF00', (5, 3): '#FF0000', (5, 4): '#FF0000', (5, 5): '#A50021',
}
RISK_RATING_COLORS = {
    'very_high': '#A50021', 'high': '#FF0000', 'medium': '#FFFF00', 'low': '#92D050', 'very_low': '#00B050',
}

# ── Parameter Coloring Rules (Likelihood, Impact, Adequacy, Effectiveness) ──
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

# ── Control Strength: 5×5 Control Matrix Colors ─────────────────────────
CONTROL_CELL_COLORS = {
    (1, 1): '#C00000', (1, 2): '#C00000', (1, 3): '#FF4B21', (1, 4): '#FF4B21', (1, 5): '#FF4B21',
    (2, 1): '#C00000', (2, 2): '#FF4B21', (2, 3): '#FF4B21', (2, 4): '#FFFF00', (2, 5): '#FFFF00',
    (3, 1): '#FF4B21', (3, 2): '#FF4B21', (3, 3): '#FFFF00', (3, 4): '#FFFF00', (3, 5): '#99FF33',
    (4, 1): '#FF4B21', (4, 2): '#FFFF00', (4, 3): '#FFFF00', (4, 4): '#99FF33', (4, 5): '#99FF33',
    (5, 1): '#FF4B21', (5, 2): '#FFFF00', (5, 3): '#99FF33', (5, 4): '#99FF33', (5, 5): '#009900',
}
CONTROL_RATING_COLORS = {
    'very_strong': '#009900', 'strong': '#99FF33', 'moderate': '#FFFF00', 'weak': '#FF4B21', 'very_weak': '#C00000',
}

# ── Residual Risk cell colors from RESIDUAL LEVEL sheet ────────────────
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
    'very_high': '#B40000', 'high': '#FF0000', 'medium': '#FFFF00', 'low': '#92D050', 'very_low': '#525252',
}


def _text_color_for_bg(bg_hex):
    """Return white text for dark backgrounds, black for light ones."""
    dark_bgs = ('#990033', '#FF0000', '#C00000', '#109F10', '#00B050', '#1B4170', '#A50021', '#B40000', '#009900', '#DF0A0A', '#525252')
    if bg_hex in dark_bgs:
        return '#FFFFFF'
    return '#000000'


class RiskExcelExportWizard(models.TransientModel):
    _name = 'risk.excel.export.wizard'
    _description = 'Risk Register Excel/PDF Export Wizard'

    export_type = fields.Selection(
        selection=[
            ('excel', 'Excel'),
            ('pdf', 'PDF'),
        ],
        string='Export Type',
        default='excel',
        required=True,
    )
    branch_id = fields.Many2one(
        'hr.branch',
        string='Branch',
        help="Filter by branch. Leave empty for all branches.",
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        help="Filter by department. Leave empty for all departments.",
    )
    risk_category_id = fields.Many2one(
        'risk.category',
        string='Risk Category',
        help="Filter by risk category. Leave empty for all categories.",
    )
    date_from = fields.Date(
        string='Date From',
        help="Filter risks identified from this date.",
    )
    date_to = fields.Date(
        string='Date To',
        help="Filter risks identified up to this date.",
    )

    # Output (Excel only)
    excel_file = fields.Binary(string='Excel File', readonly=True)
    excel_filename = fields.Char(string='Filename', readonly=True)

    def _build_domain(self):
        """Build search domain from wizard filters or active_ids context."""
        active_ids = self.env.context.get('active_ids')
        if active_ids and self.env.context.get('active_model') == 'risk.register':
            return [('id', 'in', active_ids)]

        domain = []
        if self.branch_id:
            domain.append(('branch_id', '=', self.branch_id.id))
        if self.department_id:
            domain.append(('department_id', '=', self.department_id.id))
        if self.risk_category_id:
            domain.append(('risk_category_id', '=', self.risk_category_id.id))
        if self.date_from:
            domain.append(('date_identified', '>=', self.date_from))
        if self.date_to:
            domain.append(('date_identified', '<=', self.date_to))
        return domain

    def _get_header_columns(self):
        """Return the column widths matching Register tab of IBD.xlsx."""
        return [
            ('RIN', 10),
            ('Business objectives', 20),
            ('Business Processes/Activities or Risk Area', 25),
            ('Risk Event', 35),
            ('Cause', 25),
            ('Likelihood', 12),
            ('Impact', 12),
            ('Risk Rating', 14),
            ('Existing Mitigation/control', 30),
            ('Adequacy', 12),
            ('Effectiveness', 12),
            ('Control strength', 14),
            ('Residual Risk Rating', 14),
            ('Additional Mitigation/Control Action', 30),
            ('Key Risk Indicator (KRI)', 20),
            ('Risk Owner (Departments)', 20),
            ('Progress', 12),
        ]

    def _get_cell_format(self, workbook, bg_color, align='center', bold=True):
        """Create a cell format dynamically with the appropriate font color."""
        font_color = _text_color_for_bg(bg_color)
        return workbook.add_format({
            'border': 1,
            'align': align,
            'valign': 'vcenter',
            'bg_color': bg_color,
            'font_color': font_color,
            'bold': bold,
            'font_name': 'Calibri',
            'font_size': 11,
            'text_wrap': True,
        })

    @staticmethod
    def _get_fiscal_year_label():
        """Return the Ethiopian fiscal year label based on the current date.
        Ethiopian FY runs July 8 to July 7 (Hamle 1 to Sene 30).
        E.g. if today is 2026-06-24, the FY is 2025/26.
        """
        today = date.today()
        # Ethiopian FY starts around July 8 each year
        if today.month > 7 or (today.month == 7 and today.day >= 8):
            fy_start = today.year
            fy_end = today.year + 1
        else:
            fy_start = today.year - 1
            fy_end = today.year
        return f"FY {fy_start}/{str(fy_end)[-2:]}"

    def _create_workbook_formats(self, workbook):
        """Create all shared xlsxwriter formats matching IBD.xlsx styling."""
        formats = {}

        # Peach title blocks (Rows 1-4)
        formats['peach_title'] = workbook.add_format({
            'bold': True,
            'font_name': 'Calibri',
            'font_size': 14,
            'font_color': '#3F3F76',
            'bg_color': '#FFCC99',
            'valign': 'vcenter',
            'align': 'left',
        })
        formats['logo_bg'] = workbook.add_format({
            'bg_color': '#FFFFFF',
        })

        # Header rows 5, 6, 7 formats
        formats['header_tan'] = workbook.add_format({
            'bold': True,
            'font_name': 'Calibri',
            'font_size': 11,
            'font_color': '#000000',
            'bg_color': '#D6D4CA',
            'border': 1,
            'text_wrap': True,
            'valign': 'vcenter',
            'align': 'center',
        })
        formats['header_blue_gray'] = workbook.add_format({
            'bold': True,
            'font_name': 'Calibri',
            'font_size': 11,
            'font_color': '#000000',
            'bg_color': '#D2DAE4',
            'border': 1,
            'text_wrap': True,
            'valign': 'vcenter',
            'align': 'center',
        })
        formats['header_light_gray'] = workbook.add_format({
            'bold': True,
            'font_name': 'Calibri',
            'font_size': 11,
            'font_color': '#000000',
            'bg_color': '#F2F2F2',
            'border': 1,
            'text_wrap': True,
            'valign': 'vcenter',
            'align': 'center',
        })
        formats['header_normal_white'] = workbook.add_format({
            'bold': True,
            'font_name': 'Calibri',
            'font_size': 11,
            'font_color': '#000000',
            'bg_color': '#FFFFFF',
            'border': 1,
            'text_wrap': True,
            'valign': 'vcenter',
            'align': 'center',
        })

        # Data rows formatting
        formats['cell'] = workbook.add_format({
            'border': 1,
            'text_wrap': True,
            'valign': 'vcenter',
            'align': 'left',
            'font_name': 'Calibri',
            'font_size': 11,
        })
        formats['cell_center'] = workbook.add_format({
            'border': 1,
            'text_wrap': True,
            'valign': 'vcenter',
            'align': 'center',
            'font_name': 'Calibri',
            'font_size': 11,
        })
        formats['number'] = workbook.add_format({
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
            'font_name': 'Calibri',
            'font_size': 11,
            'text_wrap': True,
        })
        return formats

    def _write_risk_row(self, workbook, worksheet, row_idx, sr_no, risk, formats):
        """Write a single risk entry formatted exactly like IBD.xlsx."""
        col = 0

        # Col A (RIN)
        worksheet.write(row_idx, col, risk.name or '', formats['cell_center'])
        col += 1

        # Col B (Business objectives)
        worksheet.write(row_idx, col, risk.business_objective or '', formats['cell'])
        col += 1

        # Col C (Business Processes/Activities or Risk Area)
        worksheet.write(row_idx, col, risk.business_process or '', formats['cell'])
        col += 1

        # Col D (Risk Event)
        worksheet.write(row_idx, col, risk.risk_event or '', formats['cell'])
        col += 1

        # Col E (Cause)
        worksheet.write(row_idx, col, risk.root_cause or '', formats['cell'])
        col += 1

        # Col F (Likelihood) - color coded based on parameter level
        l_val = int(risk.likelihood) if risk.likelihood else None
        l_text = LIKELIHOOD_EXCEL_MAP.get(risk.likelihood, '')
        l_color = LIKELIHOOD_COLORS.get(l_val, '#FFFFFF') if l_val else '#FFFFFF'
        l_fmt = self._get_cell_format(workbook, l_color)
        worksheet.write(row_idx, col, l_text, l_fmt)
        col += 1

        # Col G (Impact) - color coded based on parameter level
        i_val = int(risk.impact) if risk.impact else None
        i_text = IMPACT_EXCEL_MAP.get(risk.impact, '')
        i_color = IMPACT_COLORS.get(i_val, '#FFFFFF') if i_val else '#FFFFFF'
        i_fmt = self._get_cell_format(workbook, i_color)
        worksheet.write(row_idx, col, i_text, i_fmt)
        col += 1

        # Col H (Risk Rating) - color coded based on 5x5 matrix
        ir_label = RATING_LABELS.get(risk.inherent_risk_rating, '')
        ir_score = risk.inherent_risk_score or 0
        ir_text = f"{ir_label} ({ir_score})" if ir_label else ''
        if risk.likelihood and risk.impact:
            cell_key = (int(risk.likelihood), int(risk.impact))
            ir_color = INHERENT_RISK_CELL_COLORS.get(
                cell_key,
                RISK_RATING_COLORS.get(risk.inherent_risk_rating, '#FFFFFF')
            )
        else:
            ir_color = RISK_RATING_COLORS.get(risk.inherent_risk_rating, '#FFFFFF')
        ir_fmt = self._get_cell_format(workbook, ir_color)
        worksheet.write(row_idx, col, ir_text, ir_fmt)
        col += 1

        # Col I (Existing Mitigation/control)
        worksheet.write(row_idx, col, risk.existing_controls or '', formats['cell'])
        col += 1

        # Col J (Adequacy) - color coded based on parameter level
        a_val = int(risk.control_adequacy) if risk.control_adequacy else None
        a_text = ADEQUACY_EXCEL_MAP.get(risk.control_adequacy, '')
        a_color = ADEQUACY_COLORS.get(a_val, '#FFFFFF') if a_val else '#FFFFFF'
        a_fmt = self._get_cell_format(workbook, a_color)
        worksheet.write(row_idx, col, a_text, a_fmt)
        col += 1

        # Col K (Effectiveness) - color coded based on parameter level
        e_val = int(risk.control_effectiveness) if risk.control_effectiveness else None
        e_text = EFFECTIVENESS_EXCEL_MAP.get(risk.control_effectiveness, '')
        e_color = EFFECTIVENESS_COLORS.get(e_val, '#FFFFFF') if e_val else '#FFFFFF'
        e_fmt = self._get_cell_format(workbook, e_color)
        worksheet.write(row_idx, col, e_text, e_fmt)
        col += 1

        # Col L (Control strength) - color coded based on 5x5 matrix
        cs_label = CONTROL_LABELS.get(risk.control_strength_rating, '')
        cs_score = risk.control_strength_score or 0
        cs_text = f"{cs_label} ({cs_score})" if cs_label else ''
        if risk.control_adequacy and risk.control_effectiveness:
            ctrl_key = (int(risk.control_adequacy), int(risk.control_effectiveness))
            cs_color = CONTROL_CELL_COLORS.get(
                ctrl_key,
                CONTROL_RATING_COLORS.get(risk.control_strength_rating, '#FFFFFF')
            )
        else:
            cs_color = CONTROL_RATING_COLORS.get(risk.control_strength_rating, '#FFFFFF')
        cs_fmt = self._get_cell_format(workbook, cs_color)
        worksheet.write(row_idx, col, cs_text, cs_fmt)
        col += 1

        # Col M (Residual Risk Rating) - color coded based on RESIDUAL LEVEL sheet
        rr_label = RATING_LABELS.get(risk.residual_risk_rating, '')
        rr_score = risk.residual_risk_score or 0.0
        rr_text = f"{rr_label} ({rr_score:.1f})" if rr_label else ''
        if risk.inherent_risk_rating and risk.control_strength_rating:
            res_key = (risk.inherent_risk_rating, risk.control_strength_rating)
            rr_color = RESIDUAL_CELL_COLORS.get(
                res_key,
                RESIDUAL_RATING_COLORS.get(risk.residual_risk_rating, '#FFFFFF')
            )
        else:
            rr_color = RESIDUAL_RATING_COLORS.get(risk.residual_risk_rating, '#FFFFFF')
        rr_fmt = self._get_cell_format(workbook, rr_color)
        worksheet.write(row_idx, col, rr_text, rr_fmt)
        col += 1

        # Col N (Additional Mitigation/Control Action)
        worksheet.write(row_idx, col, risk.additional_mitigation or '', formats['cell'])
        col += 1

        # Col O (Key Risk Indicator (KRI))
        worksheet.write(row_idx, col, risk.key_risk_indicator or '', formats['cell'])
        col += 1

        # Col P (Risk Owner Departments)
        owner_dept_names = ', '.join(risk.risk_owner_ids.mapped('name')) if risk.risk_owner_ids else (risk.department_id.name or '')
        worksheet.write(
            row_idx, col,
            owner_dept_names,
            formats['cell']
        )
        col += 1

        # Col Q (Progress)
        worksheet.write(row_idx, col, STATUS_LABELS.get(risk.status, ''), formats['cell_center'])

    def _write_sheet(self, workbook, sheet_name, risks, dept_or_branch_name, formats):
        """Create and populate a single worksheet matching the IBD template layout exactly."""
        safe_name = sheet_name[:31] if len(sheet_name) > 31 else sheet_name
        worksheet = workbook.add_worksheet(safe_name)

        headers = self._get_header_columns()

        # Set column widths
        for col_idx, (header, width) in enumerate(headers):
            worksheet.set_column(col_idx, col_idx, width)

        # ── Rows 1-4: Title Block with Logo ──
        worksheet.set_row(0, 22)
        worksheet.set_row(1, 22)
        worksheet.set_row(2, 22)
        worksheet.set_row(3, 22)

        # B1:B3 Merged for Logo
        worksheet.merge_range(0, 1, 2, 1, '', formats['logo_bg'])
        # Insert image
        logo_path = get_module_resource('ahadu_risk_register', 'static', 'src', 'img', 'logo.jpeg')
        if logo_path and os.path.exists(logo_path):
            worksheet.insert_image(0, 1, logo_path, {
                'x_scale': 0.1164,
                'y_scale': 0.0801,
                'x_offset': 10,
                'y_offset': 5
            })

        # Company, Template, Year texts — dynamic fiscal year
        fy_label = self._get_fiscal_year_label()
        worksheet.write('C1', 'Ahadu Bank S.C.', formats['peach_title'])
        worksheet.write('C2', 'Risk Register Template', formats['peach_title'])
        worksheet.write('C3', fy_label, formats['peach_title'])

        # Department block on Row 4 — merge C4:E4 for long names
        dept_text = f"Department/Work Unit's Name: {dept_or_branch_name}"
        worksheet.merge_range(3, 2, 3, 4, dept_text, formats['peach_title'])

        # ── Row 5: Section Merges ──
        worksheet.set_row(4, 35)
        worksheet.merge_range(4, 0, 4, 4, 'RISK IDENTIFICATION', formats['header_tan'])
        worksheet.merge_range(4, 5, 5, 7, 'INHERENT RISK ASSESSMENT', formats['header_blue_gray'])
        # Existing Mitigation/control merged rows 5-7 (col 8)
        worksheet.merge_range(4, 8, 6, 8, 'Existing Mitigation/control', formats['header_tan'])
        worksheet.merge_range(4, 9, 5, 11, 'Existing control Assessment', formats['header_blue_gray'])
        # Residual Risk Rating merged rows 5-7 (col 12)
        worksheet.merge_range(4, 12, 6, 12, 'Residual Risk Rating', formats['header_blue_gray'])
        worksheet.merge_range(4, 13, 4, 14, '', formats['header_tan'])
        worksheet.merge_range(4, 15, 4, 16, 'RISK MONITORING\n& REVIEW', formats['header_tan'])

        # ── Row 6 & 7: Column Labels ──
        worksheet.set_row(5, 30)
        worksheet.set_row(6, 30)

        # Multi-row headers (rows 6-7, cols 0-4)
        worksheet.merge_range(5, 0, 6, 0, 'RIN', formats['header_tan'])
        worksheet.merge_range(5, 1, 6, 1, 'Business objectives', formats['header_tan'])
        worksheet.merge_range(5, 2, 6, 2, 'Business Processes/Activities\nor Risk Area', formats['header_tan'])
        worksheet.merge_range(5, 3, 6, 3, 'Risk Event', formats['header_tan'])
        worksheet.merge_range(5, 4, 6, 4, 'Cause', formats['header_tan'])

        # Inherent Risk Assessment sub-headers — row 7 (row 6 is merged under INHERENT RISK ASSESSMENT)
        worksheet.write(6, 5, 'Likelihood', formats['header_tan'])
        worksheet.write(6, 6, 'Impact', formats['header_tan'])
        worksheet.write(6, 7, 'Risk Rating', formats['header_tan'])

        # Col 8 (Existing Mitigation) already merged rows 5-7 above

        # Existing Control Assessment sub-headers — row 7 (row 6 is merged under Existing control Assessment)
        worksheet.write(6, 9, 'Adequacy', formats['header_normal_white'])
        worksheet.write(6, 10, 'Effectiveness', formats['header_normal_white'])
        worksheet.write(6, 11, 'Control strength', formats['header_tan'])

        # Col 12 (Residual Risk Rating) already merged rows 5-7 above

        # N6:Q7 are merged rows 6-7
        worksheet.merge_range(5, 13, 6, 13, 'Additional Mitigation/Control\nAction', formats['header_light_gray'])
        worksheet.merge_range(5, 14, 6, 14, 'Key Risk Indicator\n(KRI)', formats['header_light_gray'])
        worksheet.merge_range(5, 15, 6, 15, 'Risk Owner\n(Departments)', formats['header_light_gray'])
        worksheet.merge_range(5, 16, 6, 16, 'Progress', formats['header_light_gray'])

        # ── Row 8+: Data Rows ──
        for row_idx, risk in enumerate(risks, start=7):
            # Auto-height: estimate based on longest text content
            texts = [
                risk.business_objective or '',
                risk.business_process or '',
                risk.risk_event or '',
                risk.root_cause or '',
                risk.existing_controls or '',
                risk.additional_mitigation or '',
            ]
            max_len = max((len(t) for t in texts), default=0)
            # Rough estimate: 45 chars per line at ~11pt, each line ~15px
            estimated_lines = max(1, max_len // 45 + 1)
            row_height = max(30, estimated_lines * 15)
            worksheet.set_row(row_idx, row_height)
            sr_no = row_idx - 6
            self._write_risk_row(workbook, worksheet, row_idx, sr_no, risk, formats)

        # Freeze Panes at Row 8 (index 7), Column D (index 3) so that Columns A-C are sticky
        worksheet.freeze_panes(7, 3)

        # ── Signature Footer ──
        if risks:
            sig_row = 7 + len(risks) + 2  # 2 blank rows after data
            worksheet.set_row(sig_row, 30)
            sig_fmt = workbook.add_format({
                'bold': True, 'font_name': 'Calibri', 'font_size': 11,
                'bottom': 1, 'valign': 'vcenter', 'align': 'left',
            })
            # Risk Maker (left side)
            first_risk = risks[0]
            maker_name = first_risk.risk_maker_id.name or ''
            maker_text = f'Prepared By (Risk Maker): {maker_name}' if maker_name else 'Prepared By (Risk Maker):'
            worksheet.merge_range(sig_row, 0, sig_row, 7, maker_text, sig_fmt)
            # Checker (right side)
            checker_name = first_risk.checker_id.name or ''
            checker_text = f'Verified By (Risk Checker): {checker_name}' if checker_name else 'Verified By (Risk Checker):'
            worksheet.merge_range(sig_row, 8, sig_row, 16, checker_text,
                                   workbook.add_format({
                                       'bold': True, 'font_name': 'Calibri', 'font_size': 11,
                                       'bottom': 1, 'valign': 'vcenter', 'align': 'right',
                                   }))

    def action_export(self):
        """Generate Excel file matching IBD.xlsx style and download directly."""
        self.ensure_one()
        if xlsxwriter is None:
            raise UserError(_(
                "The 'xlsxwriter' Python library is required for Excel export. "
                "Please install it."
            ))

        # Build domain from filters
        domain = self._build_domain()
        risks = self.env['risk.register'].search(
            domain, order='department_id asc, date_identified asc, name asc'
        )

        if not risks:
            raise UserError(_("No risk records found matching your filter criteria."))

        # Create workbook in memory
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        formats = self._create_workbook_formats(workbook)

        # Single department / branch or multi-sheet mode
        if self.department_id or self.branch_id:
            dept_or_branch_name = ''
            if self.department_id:
                dept_or_branch_name = self.department_id.name
            else:
                dept_or_branch_name = self.branch_id.name

            sheet_name = dept_or_branch_name or 'Risk Register'
            self._write_sheet(workbook, sheet_name, risks, dept_or_branch_name, formats)

            filename = 'Risk_Register'
            if self.branch_id:
                filename += '_{}'.format(self.branch_id.name.replace(' ', '_'))
            if self.department_id:
                filename += '_{}'.format(self.department_id.name.replace(' ', '_'))
            filename += '.xlsx'
        else:
            # Multi-sheet mode: group by department
            dept_groups = {}
            no_dept_risks = self.env['risk.register']
            for risk in risks:
                if risk.department_id:
                    dept_id = risk.department_id.id
                    if dept_id not in dept_groups:
                        dept_groups[dept_id] = {
                            'name': risk.department_id.name,
                            'risks': self.env['risk.register'],
                        }
                    dept_groups[dept_id]['risks'] |= risk
                else:
                    no_dept_risks |= risk

            # Create a sheet for each department
            for dept_id, dept_data in dept_groups.items():
                dept_name = dept_data['name']
                self._write_sheet(
                    workbook, dept_name, dept_data['risks'], dept_name, formats
                )

            # If any risks without department, add them to an "Unassigned" sheet
            if no_dept_risks:
                self._write_sheet(
                    workbook, 'Unassigned',
                    no_dept_risks,
                    'Unassigned',
                    formats
                )

            filename = 'All_Departments_Risk_Register.xlsx'

        workbook.close()
        output.seek(0)

        # Save to wizard record
        self.write({
            'excel_file': base64.b64encode(output.read()),
            'excel_filename': filename,
        })

        # Return act_url to download immediately
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/?model=risk.excel.export.wizard&id={self.id}&field=excel_file&download=true&filename={filename}',
            'target': 'new',
        }

    def action_export_pdf(self):
        """Search records based on filters and call the Landscape PDF report action."""
        self.ensure_one()
        domain = self._build_domain()
        risks = self.env['risk.register'].search(
            domain, order='department_id asc, date_identified asc, name asc'
        )
        if not risks:
            raise UserError(_("No risk records found matching your filter criteria."))

        # Store filtered branch/dept info in context to display in QWeb headers
        context = dict(self.env.context)
        if self.department_id:
            context['pdf_work_unit'] = self.department_id.name
        elif self.branch_id:
            context['pdf_work_unit'] = self.branch_id.name
        else:
            context['pdf_work_unit'] = 'All Departments'

        # Trigger PDF report
        return self.env['ir.actions.report'].with_context(context)._get_report_from_name(
            'ahadu_risk_register.report_risk_register_table_document'
        ).report_action(risks)
