import sys
sys.path.append(r'C:\Program Files\Odoo18\server')
import odoo
odoo.tools.config.parse_config(['-c', r'C:\Program Files\Odoo18\server\odoo.conf'])
registry = odoo.registry('ahaduodoo')
with registry.cursor() as cr:
    env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
    
    # Simulate _get_remaining_annual_leave_days
    leave_type = env.ref('ahadu_hr_leave.ahadu_leave_type_annual', raise_if_not_found=False)
    if not leave_type:
        leave_type = env['hr.leave.type'].search(['|', ('name', '=', 'ahadu_leave_type_annual'), ('name', 'ilike', 'Annual')], limit=1)
    
    print(f'Leave Type found: {leave_type.id} - {leave_type.name}')
    
    # Just take an employee who has an allocation
    alloc = env['hr.leave.allocation'].search([('holiday_status_id', '=', leave_type.id), ('state', '=', 'validate')], limit=1)
    if alloc:
        emp = alloc.employee_id
        allocations = env['hr.leave.allocation'].search([
            ('employee_id', '=', emp.id),
            ('holiday_status_id', '=', leave_type.id),
            ('state', '=', 'validate'),
        ])
        
        print(f'Allocations found for {emp.name}: {len(allocations)}')
        for a in allocations:
            print(f'Allocation ID: {a.id}, State: {a.state}, Effective Rem: {a.effective_remaining_leaves}')
            
        total_days = sum(allocations.mapped('effective_remaining_leaves')) if allocations else 0.0
        print(f'Total days: {total_days}')
    else:
        print('No allocations found at all.')
