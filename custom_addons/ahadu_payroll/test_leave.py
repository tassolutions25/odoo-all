import sys
sys.path.append(r'C:\Program Files\Odoo18\server')
import odoo
odoo.tools.config.parse_config(['-c', r'C:\Program Files\Odoo18\server\odoo.conf'])
registry = odoo.registry('ahaduodoo')
with registry.cursor() as cr:
    env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
    leave_types = env['hr.leave.type'].search([])
    for lt in leave_types:
        print(f'{lt.id}: {lt.name}')
    
    # Also let's check one employee's allocations
    allocations = env['hr.leave.allocation'].search([('state', '=', 'validate')], limit=5)
    for a in allocations:
        print(f'Allocation: {a.id}, Emp: {a.employee_id.name}, Type: {a.holiday_status_id.name}, Effective Rem: {getattr(a, "effective_remaining_leaves", "N/A")}, Expiry: {getattr(a, "expiry_date", "N/A")}, Expired Leaves: {getattr(a, "expired_leaves", "N/A")}, State: {a.state}')
