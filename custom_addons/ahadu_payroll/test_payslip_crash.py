from odoo.tests import common
import logging

_logger = logging.getLogger(__name__)

# This script simulates the environment and calls logic
def reproduce_issue(env):
    # 1. Create Employee
    employee = env['hr.employee'].create({'name': 'Test Employee', 'work_email': 'test@example.com'})
    
    # 2. Create Structure
    struct = env['hr.payroll.structure'].search([], limit=1)
    if not struct:
        struct = env['hr.payroll.structure'].create({'name': 'Test Struct'})

    # 3. Create Contract
    contract = env['hr.contract'].create({
        'name': 'Test Contract',
        'employee_id': employee.id,
        'wage': 5000,
        'state': 'open',
        'struct_id': struct.id,
        'date_start': '2025-01-01',
    })
    
    # 4. Create Batch
    batch = env['hr.payslip.run'].create({
        'name': 'Test Batch',
        'date_start': '2025-01-01',
        'date_end': '2025-01-31',
    })
    
    # 5. Create Payslip linked to Batch
    slip = env['hr.payslip'].create({
        'name': 'Test Slip',
        'employee_id': employee.id,
        'contract_id': contract.id,
        'payslip_run_id': batch.id,
        'date_from': '2025-01-01',
        'date_to': '2025-01-31',
        'struct_id': struct.id
    })
    slip.compute_sheet()
    
    # 6. Simulate Close/Approve Logic
    # Calling action_send_payslip_email directly on slip
    print("Testing basic send_email on slip...")
    try:
        slip.action_send_payslip_email()
        print("✅ action_send_payslip_email on slip passed.")
    except Exception as e:
        print(f"❌ action_send_payslip_email failed: {e}")

    # 7. Simulate Batch Logic (sudo access)
    print("Testing batch.slip_ids.sudo().action_send_payslip_email()...")
    try:
        # Re-fetch batch to ensure link
        batch.invalidate_record_cache()
        slips = batch.slip_ids
        print(f"Batch has {len(slips)} slips. Model: {slips._name}")
        slips.sudo().action_send_payslip_email()
        print("✅ Batch automation passed.")
    except Exception as e:
        print(f"❌ Batch automation failed: {e}")

# Note: This requires Odoo shell environment. 
# Since we can't run odoo-bin shell here, we rely on mental model.
# I will output the Jinja safety fix instead.
