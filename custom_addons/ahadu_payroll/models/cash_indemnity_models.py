from odoo import models, fields, api, _
from odoo.exceptions import UserError

class CashIndemnityType(models.Model):
    _name = 'cash.indemnity.type'
    _description = 'Cash Indemnity Type'

    name = fields.Char(string="Name", required=True)
    amount = fields.Float(string="Amount (Monthly)", required=True, help="Full monthly allowance amount")
    active = fields.Boolean(default=True)

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
        self.write({'state': 'draft'})

    def action_cancel(self):
        self.write({'state': 'cancel'})

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
                type_counts = {}
                for line in record.tracking_id.line_ids:
                    if record.date_from <= line.date <= record.date_to:
                        t_id = line.indemnity_type_id.id # stored as ID for dict key
                        if t_id not in type_counts: 
                            type_counts[t_id] = {'obj': line.indemnity_type_id, 'count': 0}
                        type_counts[t_id]['count'] += 1
                
                lines_vals = []
                for t_id, data in type_counts.items():
                    type_obj = data['obj']
                    count = data['count']
                    # Calc
                    amount = (type_obj.amount / record.total_working_days) * count
                    
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
