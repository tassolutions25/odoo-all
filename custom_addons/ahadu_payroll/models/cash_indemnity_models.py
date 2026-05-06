from odoo import models, fields, api, _
from odoo.exceptions import UserError

class CashIndemnityType(models.Model):
    _name = 'cash.indemnity.type'
    _description = 'Cash Indemnity Type'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Name", required=True, tracking=True)
    amount = fields.Float(string="Amount (Monthly)", required=True, help="Full monthly allowance amount", tracking=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
    ], string="Status", default='draft', tracking=True, required=True)
    
    active = fields.Boolean(default=True, tracking=True)

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_approve(self):
        if not self.env.user.has_group('ahadu_payroll.group_ahadu_payroll_finance_manager'):
            raise UserError(_("Only HR Finance Managers can approve these rules."))
        self.write({'state': 'approved'})

    def action_draft(self):
        self.write({'state': 'draft'})

    def write(self, vals):
        for rec in self:
            if rec.state == 'approved' and not self.env.user.has_group('ahadu_payroll.group_ahadu_payroll_finance_manager'):
                raise UserError(_("You cannot modify an approved rule. Please contact an HR Finance Manager to reset it to draft."))
        return super(CashIndemnityType, self).write(vals)

class CashIndemnityTracking(models.Model):
    _name = 'cash.indemnity.tracking'
    _description = 'Cash Indemnity Tracking'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Reference", readonly=True, required=True, copy=False, default='New')
    employee_id = fields.Many2one('hr.employee', string="Employee", required=True, tracking=True)
    date_from = fields.Date(string="From Date", required=True, tracking=True)
    date_to = fields.Date(string="To Date", required=True, tracking=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('verified', 'Verified'),
        ('approved', 'Approved'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')
    ], string="Status", default='draft', tracking=True)
    
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    
    prepared_by_id = fields.Many2one('res.users', string="Prepared By", default=lambda self: self.env.user, readonly=True, tracking=True)
    prepared_date = fields.Datetime(string="Prepared Date", default=fields.Datetime.now, readonly=True, tracking=True)
    
    verified_by_id = fields.Many2one('res.users', string="Verified By", readonly=True, tracking=True)
    verified_date = fields.Datetime(string="Verified Date", readonly=True, tracking=True)
    
    approved_by_id = fields.Many2one('res.users', string="Approved By", readonly=True, tracking=True)
    approved_date = fields.Datetime(string="Approved Date", readonly=True, tracking=True)

    line_ids = fields.One2many('cash.indemnity.line', 'tracking_id', string="Tracking Lines")

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('cash.indemnity.tracking') or 'New'
        return super(CashIndemnityTracking, self).create(vals)

    def action_verify(self):
        self.write({
            'state': 'verified',
            'verified_by_id': self.env.user.id,
            'verified_date': fields.Datetime.now()
        })

    def action_approve(self):
        # 1. Update Name
        new_name = f"CIA For {self.employee_id.name} From {self.date_from} To {self.date_to}"
        
        # 2. Auto-create Calculation
        # Check if one exists first
        existing = self.env['cash.indemnity'].search([('tracking_id', '=', self.id)], limit=1)
        if not existing:
             calc = self.env['cash.indemnity'].create({
                 'employee_id': self.employee_id.id,
                 'date_from': self.date_from,
                 'date_to': self.date_to,
                 'tracking_id': self.id,
                 'company_id': self.company_id.id,
                 'name': new_name # Use the same name reference
             })
             # Auto-fetch/calculate
             calc.action_fetch_tracking_data()

        self.write({
            'state': 'approved',
            'name': new_name,
            'approved_by_id': self.env.user.id,
            'approved_date': fields.Datetime.now()
        })

    def action_done(self):
        self.write({'state': 'done'})

    def action_draft(self):
        if any(rec.state in ('approved', 'done') for rec in self):
            raise UserError(_("This cash indemnity tracking is already Approved or Done. You cannot reset it to Draft."))
        self.write({'state': 'draft'})

    def action_cancel(self):
        self.write({'state': 'cancel'})

    @api.constrains('line_ids', 'date_from', 'date_to')
    def _check_dates(self):
        for rec in self:
            for line in rec.line_ids:
                if line.date < rec.date_from or line.date > rec.date_to:
                    raise UserError(_("Line date %s is outside the header range %s to %s.") % (line.date, rec.date_from, rec.date_to))
            
            # Check unique dates
            dates = rec.line_ids.mapped('date')
            if len(dates) != len(set(dates)):
                raise UserError(_("Duplicate dates detected in tracking lines. Each day can only have one indemnity record."))

    def action_open_range_wizard(self):
        self.ensure_one()
        return {
            'name': _('Add Range of Days'),
            'type': 'ir.actions.act_window',
            'res_model': 'cash.indemnity.range.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_tracking_id': self.id,
                'default_date_from': self.date_from,
                'default_date_to': self.date_to,
            }
        }

    def action_export_daily_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/ahadu_payroll/export_ci_lines/{self.id}',
            'target': 'new',
        }

    def action_import_daily_lines(self):
        self.ensure_one()
        return {
            'name': _('Import Daily Lines'),
            'type': 'ir.actions.act_window',
            'res_model': 'cash.indemnity.import.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_tracking_id': self.id,
            }
        }


class CashIndemnityLine(models.Model):
    _name = 'cash.indemnity.line'
    _description = 'Cash Indemnity Tracking Line'

    tracking_id = fields.Many2one('cash.indemnity.tracking', string="Tracking", required=True, ondelete='cascade')
    date = fields.Date(string="Date", required=True)
    indemnity_type_id = fields.Many2one('cash.indemnity.type', string="Indemnity Type", required=True)

class CashIndemnity(models.Model):
    _name = 'cash.indemnity'
    _description = 'Cash Indemnity Calculation'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Reference", readonly=True, required=True, copy=False, default='New')
    employee_id = fields.Many2one('hr.employee', string="Employee", required=True, tracking=True)
    contract_id = fields.Many2one('hr.contract', string="Contract", compute='_compute_contract', store=True, readonly=False)
    date_from = fields.Date(string="From Date", required=True, tracking=True)
    date_to = fields.Date(string="To Date", required=True, tracking=True)
    
    tracking_id = fields.Many2one('cash.indemnity.tracking', string="Linked Tracking", domain="[('state', 'in', ['approved', 'done']), ('date_from', '>=', date_from), ('date_to', '<=', date_to), ('employee_id', '=', employee_id)]")

    total_working_days = fields.Float(string="Total Working Days", compute='_compute_working_days', store=True, help="Total working days in the period (Max 26)")
    total_amount = fields.Float(string="Total Allowance", compute='_compute_amount', store=True)
    
    line_ids = fields.One2many('cash.indemnity.detail', 'indemnity_id', string="Calculation Details")

    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')
    ], string="Status", default='draft', tracking=True)
    
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    
    approved_by_id = fields.Many2one('res.users', string="Approved By", readonly=True, tracking=True)
    approved_date = fields.Datetime(string="Approved Date", readonly=True, tracking=True)

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('cash.indemnity') or 'New'
        return super(CashIndemnity, self).create(vals)

    @api.depends('employee_id', 'date_from')
    def _compute_contract(self):
        for record in self:
            if record.employee_id and record.date_from:
                contract = self.env['hr.contract'].search([
                    ('employee_id', '=', record.employee_id.id),
                    ('state', 'in', ['open', 'close']),
                    ('date_start', '<=', record.date_to),
                    '|', ('date_end', '=', False), ('date_end', '>=', record.date_from)
                ], limit=1, order='date_start desc')
                record.contract_id = contract

    def action_fetch_tracking_data(self):
        from datetime import timedelta
        for record in self:
            # 1. Fetch Tracking if not set
            if not record.tracking_id:
                record.tracking_id = self.env['cash.indemnity.tracking'].search([
                    ('employee_id', '=', record.employee_id.id),
                    ('state', 'in', ['approved', 'done']),
                    ('date_from', '>=', record.date_from),
                    ('date_to', '<=', record.date_to)
                ], limit=1, order='create_date desc')
            
            # 2. Re-compute Working Days (Force Update)
            record._compute_working_days()
            
            # 3. Populate Details
            # Clear existing
            record.line_ids = [(5, 0, 0)]
            
            if record.tracking_id and record.total_working_days > 0:
                # Fetch leaves to skip counting days if the employee is on leave
                leaves = self.env['hr.leave'].search([
                    ('employee_id', '=', record.employee_id.id),
                    ('state', '=', 'validate'),
                    ('date_from', '<=', record.date_to),
                    ('date_to', '>=', record.date_from)
                ])
                leave_dates = set()
                for leave in leaves:
                    curr = leave.date_from.date()
                    end = leave.date_to.date()
                    while curr <= end:
                        if record.date_from <= curr <= record.date_to:
                            leave_dates.add(curr)
                        curr += timedelta(days=1)

                type_counts = {}
                for line in record.tracking_id.line_ids:
                    if record.date_from <= line.date <= record.date_to:
                        # NEW CHECK: Skip if on leave
                        if line.date in leave_dates:
                            continue
                            
                        t_id = line.indemnity_type_id.id # stored as ID for dict key
                        if t_id not in type_counts: 
                            type_counts[t_id] = {'obj': line.indemnity_type_id, 'count': 0}
                        type_counts[t_id]['count'] += 1
                
                lines_vals = []
                for t_id, data in type_counts.items():
                    type_obj = data['obj']
                    count = data['count']
                    # Calc: Cap at full monthly amount even if more days are tracked
                    amount = min(type_obj.amount, (type_obj.amount / record.total_working_days) * count)
                    
                    lines_vals.append((0, 0, {
                        'indemnity_type_id': t_id,
                        'days': count,
                        'amount': amount
                    }))
                
                record.line_ids = lines_vals
                
            # 4. Update Total (trigger compute)
            record._compute_amount()
    
    @api.depends('date_from', 'date_to', 'employee_id')
    def _compute_working_days(self):
        from datetime import timedelta
        for record in self:
            if record.date_from and record.date_to:
                start_date = record.date_from
                end_date = record.date_to
                total_days = (end_date - start_date).days + 1
                
                saturdays = 0
                sundays = 0
                holidays_count = 0
                
                # Holidays
                holiday_dates = set()
                calendar = record.employee_id.resource_calendar_id
                if calendar:
                    global_leaves = self.env['resource.calendar.leaves'].search([
                        ('calendar_id', '=', calendar.id),
                        ('date_from', '<=', end_date),
                        ('date_to', '>=', start_date),
                        ('resource_id', '=', False),
                    ])
                    for leave in global_leaves:
                        curr = leave.date_from.date()
                        end = leave.date_to.date()
                        while curr <= end:
                            if start_date <= curr <= end_date:
                                holiday_dates.add(curr)
                            curr += timedelta(days=1)
                holidays_count = len(holiday_dates)

                # Leaves
                leaves = self.env['hr.leave'].search([
                    ('employee_id', '=', record.employee_id.id),
                    ('state', '=', 'validate'),
                    ('date_from', '<=', end_date),
                    ('date_to', '>=', start_date)
                ])
                leave_dates = set()
                for leave in leaves:
                    curr = leave.date_from.date()
                    end = leave.date_to.date()
                    while curr <= end:
                        if start_date <= curr <= end_date:
                            if curr not in holiday_dates:
                                leave_dates.add(curr)
                        curr += timedelta(days=1)
                
                # Weekends
                current = start_date
                while current <= end_date:
                    is_holiday = current in holiday_dates
                    is_leave = current in leave_dates
                    if not is_holiday and not is_leave:
                        wd = current.weekday()
                        if wd == 5: saturdays += 1
                        elif wd == 6: sundays += 1
                    current += timedelta(days=1)
                
                non_working = (saturdays * 0.5) + (sundays * 1.0) + holidays_count + len(leave_dates)
                calc_working_days = total_days - non_working
                
                final_working_days = min(calc_working_days, 26.0)
                record.total_working_days = max(final_working_days, 1.0) # Avoid zero division
            else:
                record.total_working_days = 26.0

    @api.depends('line_ids.amount')
    def _compute_amount(self):
        for record in self:
            record.total_amount = sum(line.amount for line in record.line_ids)

    def action_approve(self):
        self.write({
            'state': 'approved',
            'approved_by_id': self.env.user.id,
            'approved_date': fields.Datetime.now()
        })

    def action_done(self):
        self.write({'state': 'done'})

    def action_draft(self):
        if any(rec.state in ('approved', 'done') for rec in self):
            raise UserError(_("This cash indemnity calculation is already Approved or Done. You cannot reset it to Draft."))
        self.write({'state': 'draft'})

    def action_cancel(self):
        self.write({'state': 'cancel'})

class CashIndemnityDetail(models.Model):
    _name = 'cash.indemnity.detail'
    _description = 'Cash Indemnity Calculation Detail'

    indemnity_id = fields.Many2one('cash.indemnity', string="Calculation", required=True, ondelete='cascade')
    indemnity_type_id = fields.Many2one('cash.indemnity.type', string="Type", required=True)
    days = fields.Integer(string="Days", required=True)
    amount = fields.Float(string="Amount", required=True)


class CashIndemnityRangeWizard(models.TransientModel):
    _name = 'cash.indemnity.range.wizard'
    _description = 'Wizard to add range of CI days'

    tracking_id = fields.Many2one('cash.indemnity.tracking', string="Tracking", required=True)
    indemnity_type_id = fields.Many2one('cash.indemnity.type', string="Indemnity Type", required=True)
    date_from = fields.Date(string="Start Date", required=True)
    date_to = fields.Date(string="End Date", required=True)
    
    skip_sundays = fields.Boolean(string="Skip Sundays", default=True)
    skip_holidays = fields.Boolean(string="Skip Holidays", default=True)

    def action_apply(self):
        from datetime import timedelta
        self.ensure_one()
        
        if self.date_from > self.date_to:
            raise UserError(_("Start date must be before end date."))
        
        if self.date_from < self.tracking_id.date_from or self.date_to > self.tracking_id.date_to:
            raise UserError(_("Selected range must be within the tracking period (%s to %s).") % (self.tracking_id.date_from, self.tracking_id.date_to))

        # Holidays logic
        holiday_dates = set()
        if self.skip_holidays:
            calendar = self.tracking_id.employee_id.resource_calendar_id
            if calendar:
                global_leaves = self.env['resource.calendar.leaves'].search([
                    ('calendar_id', '=', calendar.id),
                    ('date_from', '<=', self.date_to),
                    ('date_to', '>=', self.date_from),
                    ('resource_id', '=', False),
                ])
                for leave in global_leaves:
                    curr = leave.date_from.date()
                    end = leave.date_to.date()
                    while curr <= end:
                        if self.date_from <= curr <= self.date_to:
                            holiday_dates.add(curr)
                        curr += timedelta(days=1)

        # Leaves logic
        leave_dates = set()
        leaves = self.env['hr.leave'].search([
            ('employee_id', '=', self.tracking_id.employee_id.id),
            ('state', '=', 'validate'),
            ('date_from', '<=', self.date_to),
            ('date_to', '>=', self.date_from)
        ])
        for leave in leaves:
            curr = leave.date_from.date()
            end = leave.date_to.date()
            while curr <= end:
                if self.date_from <= curr <= self.date_to:
                    leave_dates.add(curr)
                curr += timedelta(days=1)

        # Existing dates to skip
        existing_dates = set(self.tracking_id.line_ids.mapped('date'))
        
        lines_to_create = []
        curr_date = self.date_from
        while curr_date <= self.date_to:
            # Check Sunday
            if self.skip_sundays and curr_date.weekday() == 6:
                curr_date += timedelta(days=1)
                continue
            
            # Check Holidays
            if self.skip_holidays and curr_date in holiday_dates:
                curr_date += timedelta(days=1)
                continue

            # Check Leaves
            if curr_date in leave_dates:
                curr_date += timedelta(days=1)
                continue
            
            # Check Duplicates
            if curr_date in existing_dates:
                curr_date += timedelta(days=1)
                continue
            
            lines_to_create.append({
                'tracking_id': self.tracking_id.id,
                'date': curr_date,
                'indemnity_type_id': self.indemnity_type_id.id
            })
            curr_date += timedelta(days=1)

        if lines_to_create:
            self.env['cash.indemnity.line'].create(lines_to_create)
            
        return {'type': 'ir.actions.act_window_close'}


class CashIndemnityImportWizard(models.TransientModel):
    _name = 'cash.indemnity.import.wizard'
    _description = 'Import Cash Indemnity Lines'

    tracking_id = fields.Many2one('cash.indemnity.tracking', string="Tracking", required=True)
    file = fields.Binary(string="Excel File", required=True)
    filename = fields.Char(string="Filename")

    def action_import(self):
        import io
        import base64
        try:
            import openpyxl
        except ImportError:
            raise UserError(_("The 'openpyxl' library is required to import Excel files. Please install it."))
        from datetime import datetime

        if not self.file:
            raise UserError(_("Please upload an Excel file."))

        file_content = base64.b64decode(self.file)
        f = io.BytesIO(file_content)
        try:
            workbook = openpyxl.load_workbook(f, data_only=True)
        except Exception as e:
            raise UserError(_("Invalid Excel file: %s") % str(e))
            
        sheet = workbook.active

        # Headers: Date, Indemnity Type
        lines_to_create = []
        for row_idx, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
            if not any(row): continue
            
            date_val = row[0]
            type_name = row[1]
            
            if not date_val or not type_name:
                continue

            # Handle date
            if isinstance(date_val, datetime):
                date_val = date_val.date()
            elif isinstance(date_val, str):
                try:
                    date_val = datetime.strptime(date_val, '%Y-%m-%d').date()
                except ValueError:
                    raise UserError(_("Invalid date format in row %s. Expected YYYY-MM-DD or Excel date.") % row_idx)
            
            # Search for type
            type_id = self.env['cash.indemnity.type'].search([('name', '=', type_name)], limit=1)
            if not type_id:
                raise UserError(_("Indemnity Type '%s' not found in row %s.") % (type_name, row_idx))
            
            lines_to_create.append({
                'tracking_id': self.tracking_id.id,
                'date': date_val,
                'indemnity_type_id': type_id.id
            })
        
        if lines_to_create:
            # The create() call will trigger the date range and unique constraints in the model
            self.env['cash.indemnity.line'].create(lines_to_create)
        
        return {'type': 'ir.actions.act_window_close'}

