# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta
import calendar
from datetime import date, timedelta

import logging

_logger = logging.getLogger(__name__)

class AhaduBackpayBatch(models.Model):
    _name = 'ahadu.backpay.batch'
    _description = 'Backpay Batch'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Description', required=True, tracking=True)
    date = fields.Date('Date', default=fields.Date.context_today, required=True)
    month = fields.Selection([
        ('1', 'January'), ('2', 'February'), ('3', 'March'), ('4', 'April'),
        ('5', 'May'), ('6', 'June'), ('7', 'July'), ('8', 'August'),
        ('9', 'September'), ('10', 'October'), ('11', 'November'), ('12', 'December')
    ], string='Backpay Month', required=True, tracking=True)
    year = fields.Integer('Backpay Year', default=lambda self: fields.Date.today().year, required=True, tracking=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('verified', 'Verified'),
        ('approved', 'Approved')
    ], string='Status', default='draft', tracking=True)

    prepared_by_id = fields.Many2one('res.users', string='Prepared By', readonly=True, tracking=True)
    prepared_on = fields.Datetime(string='Prepared On', readonly=True)
    verified_by_id = fields.Many2one('res.users', string='Verified By', readonly=True, tracking=True)
    verified_on = fields.Datetime(string='Verified On', readonly=True)
    approved_by_id = fields.Many2one('res.users', string='Approved By', readonly=True, tracking=True)
    approved_on = fields.Datetime(string='Approved On', readonly=True)

    line_ids = fields.One2many('ahadu.backpay.line', 'batch_id', string='Backpay Lines')

    total_net_difference = fields.Float('Total Net Difference', compute='_compute_totals', store=True)
    bank_transfer_done = fields.Boolean('Bank Transfer Done', default=False, tracking=True)

    @api.depends('line_ids.diff_net')
    def _compute_totals(self):
        for batch in self:
            batch.total_net_difference = sum(batch.line_ids.mapped('diff_net'))

    @api.model_create_multi
    def create(self, vals_list):
        self._check_manager_restriction()
        for vals in vals_list:
            vals['prepared_by_id'] = self.env.user.id
            vals['prepared_on'] = fields.Datetime.now()
        return super(AhaduBackpayBatch, self).create(vals_list)

    def write(self, vals):
        if any(batch.state == 'draft' for batch in self):
            if not all(k in ['state', 'message_follower_ids', 'activity_ids', 'message_ids', 
                             'prepared_by_id', 'prepared_on', 'verified_by_id', 'verified_on', 
                             'approved_by_id', 'approved_on'] for k in vals.keys()):
                self._check_manager_restriction()
        return super(AhaduBackpayBatch, self).write(vals)

    def unlink(self):
        self._check_manager_restriction()
        return super(AhaduBackpayBatch, self).unlink()

    def _check_manager_restriction(self):
        """Helper to block Managers from Maker actions."""
        if self.env.user.has_group('payroll.group_payroll_manager'):
            if not self.env.user.has_group('base.group_system'):
                from odoo.exceptions import AccessError
                raise AccessError(_("Payroll Managers are restricted from this action (Create/Edit). This action is reserved for Payroll Officers."))

    def action_verify(self):
        self.write({
            'state': 'verified',
            'verified_by_id': self.env.user.id,
            'verified_on': fields.Datetime.now()
        })

    def action_approve(self):
        if not self.env.user.has_group('payroll.group_payroll_manager'):
             raise UserError(_("Only Payroll Managers can approve backpay batches."))
        self.write({
            'state': 'approved',
            'approved_by_id': self.env.user.id,
            'approved_on': fields.Datetime.now()
        })

    def action_draft(self):
        if any(batch.state == 'approved' for batch in self):
            raise UserError(_("This backpay batch is already Approved. You cannot reset it to Draft."))
        self.write({'state': 'draft'})

    def action_calculate(self):
        for line in self.line_ids:
            line._calculate_differences()

    def action_print_tax_declaration(self):
        return {
            'type': 'ir.actions.act_url',
            'url': f'/ahadu_payroll/backpay_tax_declaration/{self.id}',
            'target': 'new',
        }

    def action_print_pension_report(self):
        return {
            'type': 'ir.actions.act_url',
            'url': f'/ahadu_payroll/backpay_pension_report/{self.id}',
            'target': 'new',
        }

    def action_print_excel(self):
        """Standard Backpay Report (Preview)."""
        return {
            'type': 'ir.actions.act_url',
            'url': f'/ahadu_payroll/backpay_excel/{self.id}',
            'target': 'new',
        }

    def action_print_bank_transfer(self):
        """Formal Bank Transfer File (ZIP). Only allowed once after approval."""
        self.ensure_one()
        if self.state != 'approved':
            raise UserError(_("You cannot generate the Bank Transfer File until the backpay batch is Approved."))
        
        if self.bank_transfer_done:
            raise UserError(_("The Bank Transfer has already been processed for this backpay batch. You cannot pay twice."))
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/ahadu_payroll/backpay_bank_transfer/{self.id}',
            'target': 'new',
        }

    def action_generate_lines(self):
        """Fetch approved CTCs for the target month/year that haven't been backpaid in this batch."""
        self._check_manager_restriction()
        self.ensure_one()
        
        target_date_start = date(int(self.year), int(self.month), 1)
        _, last_day = calendar.monthrange(target_date_start.year, target_date_start.month)
        target_date_end = date(int(self.year), int(self.month), last_day)

        # 1. Find all approved CTCs with effective date <= target_date_end
        ctcs = self.env['hr.employee.ctc'].search([
            ('state', '=', 'approved'),
            ('date', '<=', target_date_end)
        ])
        
        # 2. Filter employees who have a "Done" payslip in that month
        employees_with_ctc = ctcs.mapped('employee_id')
        payslips = self.env['hr.payslip'].search([
            ('employee_id', 'in', employees_with_ctc.ids),
            ('date_from', '>=', target_date_start),
            ('date_to', '<=', target_date_end),
            ('state', '=', 'done')
        ])
        
        # 3. Track existing CTCs in any "valid" batch and what we process in this loop
        # We search all lines in any batch that is NOT in 'draft' or 'cancelled' 
        # (Assuming 'draft' lines can be deleted/regenerated)
        already_paid_ctc_ids = self.env['ahadu.backpay.line'].search([
            ('batch_id.state', 'in', ['submitted', 'approved'])
        ]).mapped('ctc_id').ids
        
        # Also include anything currently in this batch (even if in draft)
        existing_keys = set((l.employee_id.id, l.payslip_id.id) for l in self.line_ids)
        
        # 4. Calculation Range
        # Start: 1st of Backpay Month/Year
        # End: Last day of month PRIOR to self.date (Cutoff)
        _logger.info("BACKPAY_GEN: self.month=%s, self.year=%s", self.month, self.year)
        start_date = date(int(self.year), int(self.month), 1)
        cutoff_date = self.date or fields.Date.today()
        
        # Month before cutoff
        end_month_date = cutoff_date - relativedelta(months=1)
        _, last_day = calendar.monthrange(end_month_date.year, end_month_date.month)
        end_date = date(end_month_date.year, end_month_date.month, last_day)

        if end_date < start_date:
            end_date = date(start_date.year, start_date.month, calendar.monthrange(start_date.year, start_date.month)[1])

        _logger.info("BACKPAY_GEN: StartDate=%s, EndDate=%s, Cutoff=%s", start_date, end_date, cutoff_date)

        # Source Changes (only those approved in the START month/year as per user request)
        month_end_limit = date(start_date.year, start_date.month, calendar.monthrange(start_date.year, start_date.month)[1])
        
        source_ctcs = self.env['hr.employee.ctc'].search([
            ('state', '=', 'approved'),
            ('date', '>=', start_date),
            ('date', '<=', month_end_limit)
        ])
        _logger.info("BACKPAY_GEN: Found %s CTCs between %s and %s", len(source_ctcs), start_date, month_end_limit)

        source_promotions = self.env['hr.employee.promotion'].search([
            ('state', '=', 'approved'),
            ('promotion_date', '>=', start_date),
            ('promotion_date', '<=', month_end_limit)
        ])
        _logger.info("BACKPAY_GEN: Found %s Promotions: %s", len(source_promotions), source_promotions.ids)

        employees_to_process = source_ctcs.mapped('employee_id') | source_promotions.mapped('employee_id')
        _logger.info("BACKPAY_GEN: Employees to process: %s", employees_to_process.mapped('name'))
        
        if not employees_to_process:
            return True

        # For these employees, find ALL "Done" payslips within [start_date, end_date]
        payslips = self.env['hr.payslip'].search([
            ('employee_id', 'in', employees_to_process.ids),
            ('date_to', '>=', start_date),
            ('date_from', '<=', end_date),
            ('state', '=', 'done')
        ], order='date_from asc')
        _logger.info("BACKPAY_GEN: Found %s Payslips for %s employees", len(payslips), len(employees_to_process))

        for ps in payslips:
            # Check if this employee+payslip combo is already in this batch
            if (ps.employee_id.id, ps.id) in existing_keys:
                continue

            # Find the most recent adjustment record effective for this month
            ctc = self.env['hr.employee.ctc'].search([
                ('employee_id', '=', ps.employee_id.id),
                ('state', '=', 'approved'),
                ('date', '<=', ps.date_to)
            ], order='date desc', limit=1)
            
            prom = self.env['hr.employee.promotion'].search([
                ('employee_id', '=', ps.employee_id.id),
                ('state', '=', 'approved'),
                ('promotion_date', '<=', ps.date_to)
            ], order='promotion_date desc', limit=1)

            use_p = prom and (not ctc or prom.promotion_date >= ctc.date)
            
            vals = {
                'batch_id': self.id,
                'employee_id': ps.employee_id.id,
                'payslip_id': ps.id,
                'effective_date': prom.promotion_date if use_p else (ctc.date if ctc else False),
                'ctc_id': ctc.id if ctc and not use_p else False,
                'promotion_id': prom.id if use_p else False,
            }
            
            if not ctc and not prom:
                continue

            self.env['ahadu.backpay.line'].create(vals)
            existing_keys.add((ps.employee_id.id, ps.id))
        
        return True

class AhaduBackpayLine(models.Model):
    _name = 'ahadu.backpay.line'
    _description = 'Backpay Line'

    batch_id = fields.Many2one('ahadu.backpay.batch', ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    ctc_id = fields.Many2one('hr.employee.ctc', string='CTC Adjustment')
    promotion_id = fields.Many2one('hr.employee.promotion', string='Promotion')
    payslip_id = fields.Many2one('hr.payslip', string='Reference Payslip')

    effective_date = fields.Date('Effective Date')
    
    joining_date = fields.Date(related='employee_id.contract_id.date_start', string='Date of Join')
    bank_account = fields.Char(compute='_compute_bank_account', string='Bank Account')

    # Old Values (From Original Payslip)
    old_basic = fields.Float('Old Basic')
    old_fuel_liters = fields.Float('Old Fuel (L)')
    old_fuel_rate = fields.Float('Old Fuel Rate')
    old_transport = fields.Float('Old Transport')
    old_taxable_transport = fields.Float('Old Taxable Transport')
    old_representation = fields.Float('Old Rep')
    old_housing = fields.Float('Old Housing')
    old_mobile = fields.Float('Old Mobile')
    old_hardship = fields.Float('Old Hardship')
    old_ot = fields.Float('Old OT')
    
    old_gross = fields.Float('Old Gross')
    old_taxable_gross = fields.Float('Old Taxable Gross')
    old_pension_comp = fields.Float('Old Pension (11%)')
    old_income_tax = fields.Float('Old Income Tax')
    old_pension_emp = fields.Float('Old Pension (7%)')
    old_other_deductions = fields.Float('Old Other Ded')
    old_cost_sharing = fields.Float('Old Cost Sharing')
    old_total_deductions = fields.Float('Old Total Ded')
    old_net = fields.Float('Old Net Income')

    # New Values (Recalculated)
    new_basic = fields.Float('New Basic')
    new_fuel_liters = fields.Float('New Fuel (L)')
    new_fuel_rate = fields.Float('New Fuel Rate')
    new_transport = fields.Float('New Transport')
    new_taxable_transport = fields.Float('New Taxable Transport')
    new_representation = fields.Float('New Rep')
    new_housing = fields.Float('New Housing')
    new_mobile = fields.Float('New Mobile')
    new_hardship = fields.Float('New Hardship')
    new_ot = fields.Float('New OT')

    new_gross = fields.Float('New Gross')
    new_taxable_gross = fields.Float('New Taxable Gross')
    new_pension_comp = fields.Float('New Pension (11%)')
    new_income_tax = fields.Float('New Income Tax')
    new_pension_emp = fields.Float('New Pension (7%)')
    new_other_deductions = fields.Float('New Other Ded')
    new_cost_sharing = fields.Float('New Cost Sharing')
    new_total_deductions = fields.Float('New Total Ded')
    new_net = fields.Float('New Net Income')

    # Differences
    diff_basic = fields.Float('Diff Basic', compute='_compute_diffs', store=True)
    diff_net = fields.Float('Diff Net', compute='_compute_diffs', store=True)
    diff_tax = fields.Float('Diff Tax', compute='_compute_diffs', store=True)

    diff_housing = fields.Float('Diff Housing', compute='_compute_diffs', store=True)
    diff_mobile = fields.Float('Diff Mobile', compute='_compute_diffs', store=True)
    diff_representation = fields.Float('Diff Representation', compute='_compute_diffs', store=True)
    diff_hardship = fields.Float('Diff Hardship', compute='_compute_diffs', store=True)
    diff_transport = fields.Float('Diff Transport', compute='_compute_diffs', store=True)
    diff_taxable_transport = fields.Float('Diff Taxable Transport', compute='_compute_diffs', store=True)
    diff_pension_emp = fields.Float('Diff Pension (7%)', compute='_compute_diffs', store=True)
    diff_pension_comp = fields.Float('Diff Pension (11%)', compute='_compute_diffs', store=True)
    diff_taxable_gross = fields.Float('Diff Taxable Gross', compute='_compute_diffs', store=True)
    diff_ot = fields.Float('Diff OT', compute='_compute_diffs', store=True)
    diff_cost_sharing = fields.Float('Diff Cost Sharing', compute='_compute_diffs', store=True)
    diff_other_deductions = fields.Float('Diff Other Ded', compute='_compute_diffs', store=True)

    def _compute_bank_account(self):
        for line in self:
            salary_account = line.employee_id.bank_account_ids.filtered(lambda a: a.account_type == 'salary')
            line.bank_account = salary_account[0].account_number if salary_account else ''

    @api.depends('old_net', 'new_net', 'old_basic', 'new_basic', 'old_income_tax', 'new_income_tax',
                 'old_housing', 'new_housing', 'old_mobile', 'new_mobile', 
                 'old_representation', 'new_representation', 'old_hardship', 'new_hardship',
                 'old_transport', 'new_transport', 'old_taxable_transport', 'new_taxable_transport',
                 'old_pension_emp', 'new_pension_emp', 'old_pension_comp', 'new_pension_comp',
                 'old_taxable_gross', 'new_taxable_gross', 'old_ot', 'new_ot',
                 'old_cost_sharing', 'new_cost_sharing', 'old_other_deductions', 'new_other_deductions')
    def _compute_diffs(self):
        for line in self:
            line.diff_basic = line.new_basic - line.old_basic
            line.diff_net = line.new_net - line.old_net
            line.diff_tax = line.new_income_tax - line.old_income_tax
            line.diff_housing = line.new_housing - line.old_housing
            line.diff_mobile = line.new_mobile - line.old_mobile
            line.diff_representation = line.new_representation - line.old_representation
            line.diff_hardship = line.new_hardship - line.old_hardship
            line.diff_transport = line.new_transport - line.old_transport
            line.diff_taxable_transport = line.new_taxable_transport - line.old_taxable_transport
            line.diff_pension_emp = line.new_pension_emp - line.old_pension_emp
            line.diff_pension_comp = line.new_pension_comp - line.old_pension_comp
            line.diff_taxable_gross = line.new_taxable_gross - line.old_taxable_gross
            line.diff_ot = line.new_ot - line.old_ot
            line.diff_cost_sharing = line.new_cost_sharing - line.old_cost_sharing
            line.diff_other_deductions = line.new_other_deductions - line.old_other_deductions

    def _get_region_exemption(self):
        """Helper to get region-specific transport exemption."""
        self.ensure_one()
        DEFAULT_EXEMPTION = 600.0
        region = self.employee_id.region_id
        if not region:
            return DEFAULT_EXEMPTION
        config = self.env['ahadu.payroll.region.config'].search([
            ('region_id', '=', region.id)
        ], limit=1)
        return config.transport_allowance_exemption if config else DEFAULT_EXEMPTION

    def _calculate_differences(self):
        """Main calculation logic for each line using monthly weighted averages."""
        self.ensure_one()
        if not self.payslip_id:
            return
            
        # 1. Preparation
        month_start = self.payslip_id.date_from
        month_end = self.payslip_id.date_to
        total_month_days = (month_end - month_start).days + 1
        
        # Reference original payslip lines (FULL MONTH totals)
        lines = self.payslip_id.line_ids
        def get_total(code):
            return sum(lines.filtered(lambda l: l.code == code).mapped('total'))

        # 2. Capture Old Values (Full Month totals - UNAFFECTED)
        self.old_basic = get_total('BASIC')
        self.old_transport = get_total('TRANS')
        self.old_housing = get_total('HOUSE')
        self.old_mobile = get_total('MOBILE')
        self.old_representation = get_total('REP')
        self.old_hardship = get_total('HARDSHIP')
        self.old_ot = get_total('OT')
        
        self.old_gross = get_total('GROSS')
        self.old_income_tax = get_total('TAX')
        self.old_pension_emp = get_total('PENSION_EMP')
        self.old_pension_comp = get_total('PENSION_COMP')
        self.old_cost_sharing = get_total('COST_SHARING')
        
        other_ded_total = sum(lines.filtered(lambda l: l.category_id.code == 'DED' and l.code not in ['TAX', 'PENSION_EMP']).mapped('total'))
        self.old_other_deductions = other_ded_total
        self.old_total_deductions = get_total('DED') or (self.old_income_tax + self.old_pension_emp + self.old_other_deductions)
        self.old_net = get_total('NET')
        
        self.old_taxable_transport = get_total('TRANS_TAXABLE') or max(0, self.old_transport - self._get_region_exemption())
        self.old_taxable_gross = get_total('GROSS_TAXABLE')
        if not self.old_taxable_gross:
             lop_total = get_total('LOP_LEAVE')
             penalty_total = get_total('PENALTY')
             self.old_taxable_gross = (self.old_basic - lop_total - penalty_total) + self.old_taxable_transport + self.old_representation + self.old_hardship + self.old_housing + self.old_mobile + self.old_ot

        # Old Fuel Logic
        # Fuel Price at the beginning of the month
        self.old_fuel_rate = self._get_fuel_price_at(month_start)
        # Original liters used in the month
        if self.promotion_id:
            self.old_fuel_liters = self.promotion_id.current_transport_allowance_liters
        elif self.ctc_id:
            self.old_fuel_liters = self.ctc_id.current_transport_allowance_liters
        else:
            self.old_fuel_liters = self.payslip_id._get_weighted_fuel_liters()

        # 3. Compute New Values using Monthly Weighted Average Logic
        
        # Attendance factor from original payslip (used for fuel weighting)
        lop_ratio = get_total('LOP_LEAVE') / (self.old_basic or 1.0)
        penalty_ratio = get_total('PENALTY') / (self.old_basic or 1.0)
        attendance_ratio = (1.0 - lop_ratio) if lop_ratio < 1.0 else 0.0
        
        # Get segments for the month
        segments = self.payslip_id._get_salary_and_job_segments()
        
        # Weighted Summaries
        w_basic = 0.0
        w_housing = 0.0
        w_mobile = 0.0
        w_liters = 0.0
        w_rep = 0.0
        w_hard = 0.0
        w_trans = 0.0
        
        # Fetch configurations (sorted) for correct segmental lookup
        all_ctcs = self.env['hr.employee.ctc'].search([
            ('employee_id', '=', self.employee_id.id),
            ('state', '=', 'approved'),
            ('date', '<=', month_end)
        ], order='date desc')
        
        all_proms = self.env['hr.employee.promotion'].search([
            ('employee_id', '=', self.employee_id.id),
            ('state', '=', 'approved'),
            ('promotion_date', '<=', month_end)
        ], order='promotion_date desc')

        for seg in segments:
            seg_days = seg['calendar_days']
            seg_ratio = seg_days / total_month_days
            
            # Find the adjustment active at the START of this segment
            c = all_ctcs.filtered(lambda x: x.date <= seg['start'])[:1]
            p = all_proms.filtered(lambda x: x.promotion_date <= seg['start'])[:1]
            use_p = p and (not c or p.promotion_date >= c.date)
            
            if use_p:
                sal = p.new_salary
                h = p.new_housing_allowance
                m = p.new_mobile_allowance
                lt = p.new_transport_allowance_liters
                rp = p.new_representation_allowance / 100.0
                rp_fixed = getattr(p, "new_representation_allowance_fixed", 0.0)
                hr = getattr(p.new_hardship_allowance_level_id, "value_percentage", 0.0)
            elif c:
                sal = c.new_wage
                h = c.new_housing_allowance
                m = c.new_mobile_allowance
                lt = c.new_transport_allowance_liters
                rp = c.new_representation_allowance / 100.0
                rp_fixed = getattr(c, "new_representation_allowance_fixed", 0.0)
                hr = getattr(c.new_hardship_allowance_level_id, "value_percentage", 0.0)
            else:
                if self.promotion_id:
                    sal = self.promotion_id.current_salary
                    h = self.promotion_id.current_housing_allowance
                    m = self.promotion_id.current_mobile_allowance
                    lt = self.promotion_id.current_transport_allowance_liters
                    rp = (
                        getattr(
                            self.promotion_id, "current_representation_allowance", 0.0
                        )
                        / 100.0
                    )
                    rp_fixed = getattr(
                        self.promotion_id, "current_representation_allowance_fixed", 0.0
                    )
                    hr = getattr(
                        self.promotion_id.current_hardship_allowance_level_id,
                        "value_percentage",
                        0.0,
                    )
                elif self.ctc_id:
                    sal = getattr(self.ctc_id, 'current_salary', getattr(self.ctc_id, 'current_wage', 0.0))
                    h = self.ctc_id.current_housing_allowance
                    m = self.ctc_id.current_mobile_allowance
                    lt = self.ctc_id.current_transport_allowance_liters
                    rp = (
                        getattr(self.ctc_id, "current_representation_allowance", 0.0)
                        / 100.0
                    )
                    rp_fixed = getattr(
                        self.ctc_id, "current_representation_allowance_fixed", 0.0
                    )
                    hr = getattr(
                        self.ctc_id.current_hardship_allowance_level_id,
                        "value_percentage",
                        0.0,
                    )
                else:
                    sal = self.old_basic
                    h = self.old_housing
                    m = self.old_mobile
                    lt = self.old_fuel_liters
                    rp = (
                        (self.old_representation / self.old_basic)
                        if self.old_basic
                        else 0.0
                    )
                    rp_fixed = 0.0
                    hr = (self.old_hardship / self.old_basic) if self.old_basic else 0.0

            fuel_price = self._get_fuel_price_at(seg['start'])
            
            # Accumulate Weighted Totals
            w_basic += sal * seg_ratio
            w_housing += h * seg_ratio
            w_mobile += m * seg_ratio
            w_liters += lt * seg_ratio
            if rp_fixed > 0:
                w_rep += rp_fixed * seg_ratio
            else:
                w_rep += (sal * rp) * seg_ratio
            w_hard += (sal * hr) * seg_ratio
            w_trans += (lt * attendance_ratio * fuel_price) * seg_ratio

        self.new_basic = w_basic
        self.new_housing = w_housing
        self.new_mobile = w_mobile
        self.new_representation = w_rep
        self.new_hardship = w_hard
        self.new_fuel_liters = w_liters * attendance_ratio
        self.new_fuel_rate = self._get_weighted_fuel_rate(month_start, month_end) # Monthly Average
        self.new_transport = w_trans
        self.new_ot = self.old_ot
        
        self.new_gross = self.new_basic + self.new_transport + self.new_housing + self.new_mobile + self.new_representation + self.new_hardship + self.new_ot
        
        exemption = self._get_region_exemption()
        self.new_taxable_transport = max(0, self.new_transport - exemption)
        
        earned_basic = w_basic * (1.0 - lop_ratio - penalty_ratio)
        self.new_taxable_gross = earned_basic + self.new_taxable_transport + self.new_representation + self.new_hardship + self.new_housing + self.new_mobile + self.new_ot
        
        self.new_income_tax = self._get_ahadu_income_tax(self.new_taxable_gross)
        self.new_pension_emp = self.new_basic * 0.07
        self.new_pension_comp = self.new_basic * 0.11
        
        self.new_other_deductions = self.old_other_deductions
        self.new_cost_sharing = self.old_cost_sharing
        self.new_total_deductions = self.new_income_tax + self.new_pension_emp + self.new_other_deductions
        self.new_net = self.new_gross - self.new_total_deductions

    def _get_fuel_price_at(self, check_date):
        """Get the fuel price active at a specific date."""
        history = self.env['ahadu.fuel.price.history'].search([
            ('company_id', '=', self.employee_id.company_id.id),
            ('effective_date', '<=', check_date)
        ], order='effective_date desc', limit=1)
        if history:
            return history.price
        return float(self.env['ir.config_parameter'].sudo().get_param('ahadu_hr.fuel_price_per_liter', default=0.0))

    def _get_weighted_fuel_rate(self, date_from, date_to):
        """Calculate weighted average fuel rate for a period"""
        history = self.env['ahadu.fuel.price.history'].search([
            ('company_id', '=', self.employee_id.company_id.id),
            ('effective_date', '<=', date_to)
        ], order='effective_date asc')
        
        if not history:
            return float(self.env['ir.config_parameter'].sudo().get_param('ahadu_hr.fuel_price_per_liter', default=0.0))
            
        # Filter relevant history records
        relevant_history = []
        # Add the state at the beginning (last change before date_from)
        pre_history = self.env['ahadu.fuel.price.history'].search([
            ('company_id', '=', self.employee_id.company_id.id),
            ('effective_date', '<', date_from)
        ], order='effective_date desc', limit=1)
        
        current_price = pre_history.price if pre_history else history[0].price
        current_start = date_from
        
        total_weighted_price = 0.0
        total_days = (date_to - date_from).days + 1
        
        for h in history.filtered(lambda x: x.effective_date >= date_from):
            # Period before this change
            days = (h.effective_date - current_start).days
            total_weighted_price += current_price * days
            current_price = h.price
            current_start = h.effective_date
            
        # Final period
        days = (date_to - current_start).days + 1
        total_weighted_price += current_price * days
        
        return total_weighted_price / total_days

    def _get_ahadu_income_tax(self, taxable_income):
        """Replicated Ethiopian Tax rule"""
        tax = 0.0
        brackets = self.env['ahadu.payroll.tax.bracket'].search([
            ('active', '=', True)
        ], order='lower_bound asc')
        
        for bracket in brackets:
            lower = bracket.lower_bound
            upper = bracket.upper_bound
            
            is_match = False
            if upper > 0:
                if lower <= taxable_income <= upper:
                    is_match = True
            else:
                if taxable_income >= lower:
                    is_match = True
            
            if is_match:
                tax = (taxable_income * (bracket.rate / 100.0)) - bracket.deduction
                break
                
        return round(max(0, tax), 2)
