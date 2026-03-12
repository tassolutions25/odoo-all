from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import timedelta, datetime, time
import pytz

class AhaduOvertimeRule(models.Model):
    _name = 'ahadu.overtime.rule'
    _description = 'Dynamic Overtime Rule'
    _order = 'sequence, id'

    name = fields.Char(string="Name", required=True)
    sequence = fields.Integer(string="Sequence", default=10)
    dayofweek = fields.Selection([
        ('0', 'Monday'),
        ('1', 'Tuesday'),
        ('2', 'Wednesday'),
        ('3', 'Thursday'),
        ('4', 'Friday'),
        ('5', 'Saturday'),
        ('6', 'Sunday'),
    ], string="Day of Week", required=True)
    
    time_start = fields.Float(string="Start Time", required=True, help="e.g. 17.5 for 5:30 PM")
    time_end = fields.Float(string="End Time", required=True, help="e.g. 6.0 for 6:00 AM (next day if < Start)")
    
    type = fields.Selection([
        ('normal', 'Normal'),
        ('night', 'Night'),
        ('weekend', 'Weekend'),
    ], string="Overtime Type", required=True, default='normal')
    
    active = fields.Boolean(default=True)

class AhaduOvertimeTracking(models.Model):
    _name = 'ahadu.overtime.tracking'
    _description = 'Overtime Tracking'
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

    # Actors
    prepared_by_id = fields.Many2one('res.users', string="Prepared By", default=lambda self: self.env.user, readonly=True, tracking=True)
    verified_by_id = fields.Many2one('res.users', string="Verified By", readonly=True, tracking=True)
    approved_by_id = fields.Many2one('res.users', string="Approved By", readonly=True, tracking=True)

    line_ids = fields.One2many('ahadu.overtime.tracking.line', 'tracking_id', string="Tracking Lines")
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)

    @api.model
    def create(self, vals):
        if vals.get('employee_id') and vals.get('date_from'):
            employee = self.env['hr.employee'].browse(vals['employee_id'])
            date_from = fields.Date.from_string(vals['date_from'])
            vals['name'] = "OT for %s for %s" % (employee.name, date_from.strftime('%B %Y'))
        elif vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('ahadu.overtime.tracking') or 'New'
        return super(AhaduOvertimeTracking, self).create(vals)

    def action_verify(self):
        self.ensure_one()
        self.write({
            'state': 'verified', 
            'verified_by_id': self.env.user.id
        })

    def action_approve(self):
        self.ensure_one()
        self.write({
            'state': 'approved', 
            'approved_by_id': self.env.user.id
        })
        # Auto-create Calculation
        existing = self.env['ahadu.overtime'].search([
            ('tracking_id', '=', self.id)
        ], limit=1)
        if not existing:
            calc = self.env['ahadu.overtime'].create({
                'employee_id': self.employee_id.id,
                'date_from': self.date_from,
                'date_to': self.date_to,
                'tracking_id': self.id,
                'company_id': self.company_id.id
            })
            calc.action_fetch_tracking_data()

    def action_done(self):
        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'cancel'})

    def action_draft(self):
        self.write({'state': 'draft'})


class AhaduOvertimeTrackingLine(models.Model):
    _name = 'ahadu.overtime.tracking.line'
    _description = 'Overtime Tracking Line'

    tracking_id = fields.Many2one('ahadu.overtime.tracking', string="Tracking", required=True, ondelete='cascade')
    
    date = fields.Date(string="Date", required=True, default=fields.Date.context_today)

    # 12-Hour Selection Fields
    
    # Start Logic
    start_hour = fields.Selection([
        ('01', '01'), ('02', '02'), ('03', '03'), ('04', '04'),
        ('05', '05'), ('06', '06'), ('07', '07'), ('08', '08'),
        ('09', '09'), ('10', '10'), ('11', '11'), ('12', '12')
    ], string="Start Hour", required=True, default='08')
    
    start_minute = fields.Selection([
        ('00', '00'), ('05', '05'), ('10', '10'), ('15', '15'),
        ('20', '20'), ('25', '25'), ('30', '30'), ('35', '35'),
        ('40', '40'), ('45', '45'), ('50', '50'), ('55', '55')
    ], string="Start Minute", required=True, default='00')
    
    start_am_pm = fields.Selection([
        ('am', 'AM'), ('pm', 'PM')
    ], string="Start AM/PM", required=True, default='am')


    # End Logic
    end_hour = fields.Selection([
        ('01', '01'), ('02', '02'), ('03', '03'), ('04', '04'),
        ('05', '05'), ('06', '06'), ('07', '07'), ('08', '08'),
        ('09', '09'), ('10', '10'), ('11', '11'), ('12', '12')
    ], string="End Hour", required=True, default='05')
    
    end_minute = fields.Selection([
        ('00', '00'), ('05', '05'), ('10', '10'), ('15', '15'),
        ('20', '20'), ('25', '25'), ('30', '30'), ('35', '35'),
        ('40', '40'), ('45', '45'), ('50', '50'), ('55', '55')
    ], string="End Minute", required=True, default='00')

    end_am_pm = fields.Selection([
        ('am', 'AM'), ('pm', 'PM')
    ], string="End AM/PM", required=True, default='pm')

    # Computed Store for Calculation (Internal Use)
    total_hours = fields.Float(string="Total Hours", compute='_compute_hours_split', store=True)
    
    # Split Hours
    normal_hours = fields.Float(string="Normal (1.5)", compute='_compute_hours_split', store=True)
    night_hours = fields.Float(string="Night (1.75)", compute='_compute_hours_split', store=True)
    weekend_hours = fields.Float(string="Weekend (2.0)", compute='_compute_hours_split', store=True)
    holiday_hours = fields.Float(string="Holiday (2.5)", compute='_compute_hours_split', store=True)

    def _convert_to_24h(self, hour_str, minute_str, am_pm):
        """Helper to convert 12h selection to 24h integer tuple"""
        h = int(hour_str)
        m = int(minute_str)
        if am_pm == 'pm' and h != 12:
            h += 12
        elif am_pm == 'am' and h == 12:
            h = 0
        return h, m

    @api.depends('date', 'start_hour', 'start_minute', 'start_am_pm', 'end_hour', 'end_minute', 'end_am_pm')
    def _compute_hours_split(self):
        # 1. Fetch Rules
        rules = self.env['ahadu.overtime.rule'].search([])
        
        # 2. Iterate Lines
        for line in self:
            if not (line.date and line.start_hour and line.start_minute and line.start_am_pm and 
                    line.end_hour and line.end_minute and line.end_am_pm):
                line.total_hours = 0
                line.normal_hours = 0
                line.night_hours = 0
                line.weekend_hours = 0
                line.holiday_hours = 0
                continue
            
            # Construct Datetimes
            s_h, s_m = self._convert_to_24h(line.start_hour, line.start_minute, line.start_am_pm)
            e_h, e_m = self._convert_to_24h(line.end_hour, line.end_minute, line.end_am_pm)
            
            start_dt = datetime.combine(line.date, time(s_h, s_m))
            end_dt = datetime.combine(line.date, time(e_h, e_m))
            
            # Cross-midnight check
            if end_dt <= start_dt:
                end_dt += timedelta(days=1)
                
            duration_hours = (end_dt - start_dt).total_seconds() / 3600.0
            line.total_hours = duration_hours
            
            normal = 0.0
            night = 0.0
            weekend = 0.0
            holiday = 0.0
            
            curr = start_dt
            
            # Optimization: Collect ALL relevant boundaries for the span
            # Days involved: start_date to end_date (could be +1)
            relevant_days = []
            d = start_dt.date()
            while d <= end_dt.date():
                relevant_days.append(d)
                d += timedelta(days=1)
            
            # Collect Cuts: Start/End of OT, Midnights, Rule Changes
            cuts = {start_dt, end_dt}
            
            for d_date in relevant_days:
                # Midnight
                midnight = datetime.combine(d_date, time(0,0))
                cuts.add(midnight)
                next_midnight = midnight + timedelta(days=1)
                cuts.add(next_midnight)
                
                # Rule Boundaries
                # Map date weekday to rules
                day_str = str(d_date.weekday()) # 0=Mon
                day_rules = rules.filtered(lambda r: r.dayofweek == day_str)
                
                for r in day_rules:
                    # Start
                    h_start = int(r.time_start)
                    m_start = int((r.time_start - h_start) * 60)
                    cuts.add(datetime.combine(d_date, time(h_start, m_start)))
                    
                    # End
                    h_end = int(r.time_end)
                    m_end = int((r.time_end - h_end) * 60)
                    cuts.add(datetime.combine(d_date, time(h_end, m_end)))

            # Sort cuts and iterate intervals
            sorted_cuts = sorted([c for c in cuts if start_dt <= c <= end_dt])
            
            for i in range(len(sorted_cuts) - 1):
                t1 = sorted_cuts[i]
                t2 = sorted_cuts[i+1]
                if t1 >= t2: continue
                
                seg_hours = (t2 - t1).total_seconds() / 3600.0
                if seg_hours <= 0: continue
                
                # Check Midpoint for classification
                mid = t1 + (t2 - t1) / 2
                mid_date = mid.date()
                mid_time = mid.hour + mid.minute / 60.0
                mid_weekday = str(mid_date.weekday())
                
                # 1. Holiday Check (Highest Priority)
                is_holiday = self.env['resource.calendar.leaves'].search_count([
                    ('resource_id', '=', False),
                    ('date_from', '<=', mid_date), 
                    ('date_to', '>=', mid_date)
                ]) > 0
                
                if is_holiday:
                    holiday += seg_hours
                    continue

                # 2. Rule Check
                # Find first matching rule
                # Logic: Is mid_time within Rule?
                # Need to check constraints for Day-of-Week AND Previous Day Overnight
                
                matched_type = None
                
                # A. Rules for Current Day
                # Valid if: Start <= Mid < End  OR (Start > End (overnight) AND Start <= Mid)
                daily_rules = rules.filtered(lambda r: r.dayofweek == mid_weekday)
                for r in daily_rules:
                    if r.time_start <= r.time_end:
                        if r.time_start <= mid_time < r.time_end:
                            matched_type = r.type
                            break
                    else:
                        # Overnight starts today
                        if r.time_start <= mid_time:
                            matched_type = r.type
                            break
                
                # B. If no match, check Previous Day Overnight Rule
                # Valid if: Prev Rule Start > Prev Rule End AND Mid < Prev Rule End
                if not matched_type:
                    prev_date = mid_date - timedelta(days=1)
                    prev_weekday = str(prev_date.weekday())
                    prev_rules = rules.filtered(lambda r: r.dayofweek == prev_weekday)
                    for r in prev_rules:
                        if r.time_start > r.time_end:
                            if mid_time < r.time_end:
                                matched_type = r.type
                                break
                
                # Apply Match
                if matched_type == 'night':
                    night += seg_hours
                elif matched_type == 'weekend':
                    weekend += seg_hours
                elif matched_type == 'normal':
                    normal += seg_hours
                elif matched_type == 'holiday':
                    holiday += seg_hours # Explicit rule
                # Else: No match = Ignored/Regular work? 
                # Or fallback?
                # User implied explicit rules. If no rule, it's not OT.
            
            line.normal_hours = normal
            line.night_hours = night
            line.weekend_hours = weekend
            line.holiday_hours = holiday


class AhaduOvertime(models.Model):
    _name = 'ahadu.overtime'
    _description = 'Overtime Output'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Reference", readonly=True, required=True, copy=False, default='New')
    
    # Link to Tracking
    tracking_id = fields.Many2one('ahadu.overtime.tracking', string="Linked Tracking", domain="[('state', 'in', ['approved', 'done']), ('date_from', '>=', date_from), ('date_to', '<=', date_to), ('employee_id', '=', employee_id)]")
    
    employee_id = fields.Many2one('hr.employee', string="Employee", required=True, tracking=True)
    contract_id = fields.Many2one('hr.contract', string="Contract", compute='_compute_contract', store=True, readonly=False)
    date_from = fields.Date(string="From Date", required=True, tracking=True)
    date_to = fields.Date(string="To Date", required=True, tracking=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')
    ], string="Status", default='draft', tracking=True)
    
    approved_by_id = fields.Many2one('res.users', string="Approved By", readonly=True, tracking=True)

    # Calculation Fields
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True)
    wage = fields.Monetary(string="Basic Salary", related='employee_id.emp_wage', store=True, currency_field='currency_id')
    
    total_calendar_days = fields.Integer(string="Total Calendar Days", compute='_compute_days', store=True)
    saturdays = fields.Integer(string="Saturdays", compute='_compute_days', store=True)
    sundays = fields.Integer(string="Sundays", compute='_compute_days', store=True)
    holidays = fields.Integer(string="Holidays", compute='_compute_days', store=True)
    
    # Hours Calculation
    gross_possible_hours = fields.Float(string="Gross Possible Hours", compute='_compute_hours', store=True, help="Total Calendar Days * 8")
    off_hours_saturday = fields.Float(string="Off Hours (Saturday)", compute='_compute_hours', store=True)
    off_hours_sunday = fields.Float(string="Off Hours (Sunday)", compute='_compute_hours', store=True)
    off_hours_holiday = fields.Float(string="Off Hours (Holiday)", compute='_compute_hours', store=True)
    total_off_hours = fields.Float(string="Total Off Hours", compute='_compute_hours', store=True)
    
    total_working_hours = fields.Float(string="Total Working Hours", compute='_compute_hours', store=True, help="Gross - Total Off")
    hourly_rate = fields.Monetary(string="Rate Per Hr", compute='_compute_rate', store=True, help="Basic Salary / Total Working Hours", currency_field='currency_id')
    
    line_ids = fields.One2many('ahadu.overtime.line', 'overtime_id', string="Overtime Details")
    
    total_overtime_amount = fields.Monetary(string="Total Overtime Amount", compute='_compute_total', store=True, currency_field='currency_id')

    @api.model
    def create(self, vals):
        if vals.get('employee_id') and vals.get('date_from'):
            employee = self.env['hr.employee'].browse(vals['employee_id'])
            date_from = fields.Date.from_string(vals['date_from'])
            vals['name'] = "OT for %s for %s" % (employee.name, date_from.strftime('%B %Y'))
        elif vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('ahadu.overtime') or 'New'
        return super(AhaduOvertime, self).create(vals)

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

    @api.depends('date_from', 'date_to')
    def _compute_days(self):
        for record in self:
            if record.date_from and record.date_to:
                start_date = record.date_from
                end_date = record.date_to
                
                delta = end_date - start_date
                total_days = delta.days + 1
                record.total_calendar_days = total_days
                
                saturdays = 0
                sundays = 0
                holidays = 0
                
                holiday_leaves = self.env['resource.calendar.leaves'].search([
                    ('resource_id', '=', False), # Global
                    ('date_from', '<=', end_date),
                    ('date_to', '>=', start_date)
                ])
                
                holiday_dates = set()
                for leave in holiday_leaves:
                    d_from = leave.date_from.date()
                    d_to = leave.date_to.date()
                    current = d_from
                    while current <= d_to:
                        if start_date <= current <= end_date:
                            holiday_dates.add(current)
                        current += timedelta(days=1)
                
                current_date = start_date
                while current_date <= end_date:
                    is_holiday = current_date in holiday_dates
                    if is_holiday:
                        holidays += 1
                    else:
                        if current_date.weekday() == 5: # Saturday
                            saturdays += 1
                        elif current_date.weekday() == 6: # Sunday
                            sundays += 1
                    
                    current_date += timedelta(days=1)
                
                record.saturdays = saturdays
                record.sundays = sundays
                record.holidays = holidays
            else:
                record.total_calendar_days = 0
                record.saturdays = 0
                record.sundays = 0
                record.holidays = 0

    @api.depends('total_calendar_days', 'saturdays', 'sundays', 'holidays')
    def _compute_hours(self):
        for record in self:
            record.gross_possible_hours = record.total_calendar_days * 8.0
            record.off_hours_saturday = record.saturdays * 4.0
            record.off_hours_sunday = record.sundays * 8.0
            record.off_hours_holiday = record.holidays * 8.0
            record.total_off_hours = record.off_hours_saturday + record.off_hours_sunday + record.off_hours_holiday
            record.total_working_hours = record.gross_possible_hours - record.total_off_hours

    @api.depends('wage', 'total_working_hours')
    def _compute_rate(self):
        for record in self:
            if record.total_working_hours > 0:
                record.hourly_rate = record.wage / record.total_working_hours
            else:
                record.hourly_rate = 0.0

    @api.depends('line_ids.amount')
    def _compute_total(self):
        for record in self:
            record.total_overtime_amount = sum(line.amount for line in record.line_ids)

    def action_fetch_tracking_data(self):
        for record in self:
            if not record.tracking_id:
                # Optionally search for one if not linked
                record.tracking_id = self.env['ahadu.overtime.tracking'].search([
                    ('employee_id', '=', record.employee_id.id),
                    ('state', 'in', ['approved', 'done']),
                    ('date_from', '>=', record.date_from),
                    ('date_to', '<=', record.date_to)
                ], limit=1, order='create_date desc')
            
            if record.tracking_id:
                # Use stored values from tracking
                record.line_ids.unlink()
                lines_created = 0
                
                for t_line in record.tracking_id.line_ids:
                    
                    if t_line.date < record.date_from or t_line.date > record.date_to:
                        continue
                        
                    if t_line.normal_hours > 0:
                        self.env['ahadu.overtime.line'].create({
                            'overtime_id': record.id,
                            'date': t_line.date,
                            'type': 'normal',
                            'hours': t_line.normal_hours
                        })
                        lines_created += 1
                    if t_line.night_hours > 0:
                        self.env['ahadu.overtime.line'].create({
                            'overtime_id': record.id,
                            'date': t_line.date,
                            'type': 'night',
                            'hours': t_line.night_hours
                        })
                        lines_created += 1
                    if t_line.weekend_hours > 0:
                        self.env['ahadu.overtime.line'].create({
                            'overtime_id': record.id,
                            'date': t_line.date,
                            'type': 'weekend',
                            'hours': t_line.weekend_hours
                        })
                        lines_created += 1
                    if t_line.holiday_hours > 0:
                        self.env['ahadu.overtime.line'].create({
                            'overtime_id': record.id,
                            'date': t_line.date,
                            'type': 'holiday',
                            'hours': t_line.holiday_hours
                        })
                        lines_created += 1
                
                if lines_created == 0:
                    # Warning if tracking found but no OT logic matched
                    raise UserError(_("Tracking record found, but no Overtime Hours were calculated. Please check the Start/End times on the tracking sheet. (Note: Regular working hours e.g. 8am-5pm on weekdays are NOT overtime)."))
            else:
                 raise UserError(_("No Approved or Done Tracking record found for this employee and period."))
    def action_approve(self):
        self.write({
            'state': 'approved',
            'approved_by_id': self.env.user.id
        })

    def action_done(self):
        self.write({'state': 'done'})
    
    def action_draft(self):
        self.write({'state': 'draft'})


class AhaduOvertimeLine(models.Model):
    _name = 'ahadu.overtime.line'
    _description = 'Overtime Line'

    overtime_id = fields.Many2one('ahadu.overtime', string="Overtime Request", required=True, ondelete='cascade')
    date = fields.Date(string="Date", required=True)
    type = fields.Selection([
        ('normal', 'Normal (1.5)'),
        ('night', 'Night (1.75)'),
        ('weekend', 'Weekend (2.0)'),
        ('holiday', 'Holiday (2.5)')
    ], string="Type", required=True, default='normal')
    
    hours = fields.Float(string="Duration (Hours)", required=True)
    rate = fields.Float(string="Rate", compute='_compute_rate', store=True, readonly=True)
    currency_id = fields.Many2one('res.currency', related='overtime_id.currency_id')
    amount = fields.Monetary(string="Amount", compute='_compute_amount', store=True, currency_field='currency_id')

    @api.depends('type')
    def _compute_rate(self):
        # Fetch rates from Config (with defaults)
        Config = self.env['ir.config_parameter'].sudo()
        r_normal = float(Config.get_param('ahadu_payroll.ot_rate_normal', 1.5))
        r_night = float(Config.get_param('ahadu_payroll.ot_rate_night', 1.75))
        r_weekend = float(Config.get_param('ahadu_payroll.ot_rate_weekend', 2.0))
        r_holiday = float(Config.get_param('ahadu_payroll.ot_rate_holiday', 2.5))
        
        rates = {
            'normal': r_normal,
            'night': r_night,
            'weekend': r_weekend,
            'holiday': r_holiday,
        }
        for line in self:
            line.rate = rates.get(line.type, 1.0)

    @api.depends('hours', 'rate', 'overtime_id.hourly_rate')
    def _compute_amount(self):
        for line in self:
            line.amount = line.hours * line.rate * line.overtime_id.hourly_rate
