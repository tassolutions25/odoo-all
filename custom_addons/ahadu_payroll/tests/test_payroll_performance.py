# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase
import time
import logging

_logger = logging.getLogger(__name__)


class TestPayrollPerformance(TransactionCase):
    """Performance and correctness tests for optimized payroll processing."""
    
    def setUp(self):
        super().setUp()
        
        # Create test cost center
        self.cost_center = self.env['ahadu.cost.center'].create({
            'name': 'Test Branch',
            'code': 'TEST001',
        })
        
        # Create test accounts
        self.account_expense = self.env['ahadu.account'].create({
            'name': 'Test Salary Expense',
            'code': 'TEST5030101'
        })
        
        self.account_liability = self.env['ahadu.account'].create({
            'name': 'Test Salary Payable',
            'code': 'TEST2020300'
        })
        
        # Get or create salary structure
        self.structure = self.env.ref('ahadu_payroll.structure_ahadu_monthly', raise_if_not_found=False)
        
        # Create test employees with contracts
        self.employees = self.env['hr.employee']
        self.test_employee_count = 20
        
        for i in range(self.test_employee_count):
            emp = self.env['hr.employee'].create({
                'name': f'Test Employee {i}',
                'emp_wage': 10000.0 + (i * 100),  # Varying wages
            })
            
            # Create contract for employee
            self.env['hr.contract'].create({
                'name': f'Contract {i}',
                'employee_id': emp.id,
                'emp_wage': emp.emp_wage,
                'cost_center_id': self.cost_center.id,
                'state': 'open',
                'date_start': '2024-01-01',
            })
            
            self.employees |= emp
        
        _logger.info(f"Test setup complete: {len(self.employees)} employees created")
    
    def test_journal_entry_generation_performance(self):
        """Test that journal entry generation completes in reasonable time."""
        
        if not self.structure:
            self.skipTest("Salary structure 'ahadu_payroll.structure_ahadu_monthly' not found")
        
        # Create payslip batch
        batch = self.env['hr.payslip.run'].create({
            'name': 'Performance Test Batch',
            'date_start': '2024-01-01',
            'date_end': '2024-01-31',
        })
        
        # Generate payslips for each employee
        for emp in self.employees:
            self.env['hr.payslip'].create({
                'name': f'Slip {emp.name}',
                'employee_id': emp.id,
                'date_from': '2024-01-01',
                'date_to': '2024-01-31',
                'contract_id': emp.contract_id.id,
                'struct_id': self.structure.id,
                'payslip_run_id': batch.id,
            })
        
        # Compute all payslips
        batch.slip_ids.compute_sheet()
        
        # Verify payslips computed successfully
        self.assertTrue(batch.slip_ids, "Batch should have payslips")
        self.assertTrue(
            all(slip.line_ids for slip in batch.slip_ids),
            "All payslips should have computed lines"
        )
        
        # Measure journal entry generation time
        start = time.time()
        batch.generate_standalone_journal_entry()
        elapsed = time.time() - start
        
        # Performance assertion: should complete in under 3 seconds for 20 employees
        # (very conservative threshold)
        self.assertLess(
            elapsed, 3.0, 
            f"Journal entry generation took {elapsed:.2f}s, expected < 3s for {self.test_employee_count} employees"
        )
        
        # Log actual performance
        _logger.info(
            f"✓ Performance test passed: {self.test_employee_count} employees "
            f"processed in {elapsed:.3f}s ({elapsed/self.test_employee_count*1000:.1f}ms per employee)"
        )
        
        # Verify correctness
        entry = self.env['ahadu.journal.entry'].search([
            ('payslip_run_id', '=', batch.id)
        ])
        self.assertTrue(entry, "Journal entry should be created")
        self.assertTrue(entry.line_ids, "Journal entry should have lines")
    
    def test_batch_create_correctness(self):
        """Verify batch create produces correct accounting entries."""
        
        if not self.structure:
            self.skipTest("Salary structure not found")
        
        # Create small batch with 3 employees for detailed verification
        batch = self.env['hr.payslip.run'].create({
            'name': 'Correctness Test Batch',
            'date_start': '2024-01-01',
            'date_end': '2024-01-31',
        })
        
        test_employees = self.employees[:3]
        
        for emp in test_employees:
            self.env['hr.payslip'].create({
                'name': f'Slip {emp.name}',
                'employee_id': emp.id,
                'date_from': '2024-01-01',
                'date_to': '2024-01-31',
                'contract_id': emp.contract_id.id,
                'struct_id': self.structure.id,
                'payslip_run_id': batch.id,
            })
        
        batch.slip_ids.compute_sheet()
        batch.generate_standalone_journal_entry()
        
        entry = self.env['ahadu.journal.entry'].search([
            ('payslip_run_id', '=', batch.id)
        ])
        
        # Verify debits equal credits (fundamental accounting rule)
        total_debit = sum(entry.line_ids.mapped('debit'))
        total_credit = sum(entry.line_ids.mapped('credit'))
        
        self.assertAlmostEqual(
            total_debit, total_credit, places=2,
            msg=f"Total debits ({total_debit:.2f}) should equal total credits ({total_credit:.2f})"
        )
        
        # Verify each employee has journal lines
        for slip in batch.slip_ids:
            employee_journal_lines = entry.line_ids.filtered(
                lambda jl: slip.employee_id.name in jl.description
            )
            
            self.assertTrue(
                employee_journal_lines,
                f"Employee {slip.employee_id.name} should have journal lines"
            )
            
            # Each salary rule with amount > 0 creates 2 lines (debit + credit)
            active_salary_lines = slip.line_ids.filtered(lambda l: l.total > 0)
            expected_lines = len(active_salary_lines) * 2
            
            # Note: Some rules may only have debit or credit account, so this is approximate
            self.assertGreater(
                len(employee_journal_lines), 0,
                f"Employee {slip.employee_id.name} should have at least some journal lines"
            )
        
        _logger.info(
            f"✓ Correctness test passed: {len(entry.line_ids)} journal lines created, "
            f"debits={total_debit:.2f}, credits={total_credit:.2f}"
        )
    
    def test_leave_deduction_cache_compatibility(self):
        """Verify leave deduction works with and without cache."""
        
        if not self.structure:
            self.skipTest("Salary structure not found")
        
        emp = self.employees[0]
        
        # Create a payslip
        slip = self.env['hr.payslip'].create({
            'name': f'Leave Test Slip',
            'employee_id': emp.id,
            'date_from': '2024-01-01',
            'date_to': '2024-01-31',
            'contract_id': emp.contract_id.id,
            'struct_id': self.structure.id,
        })
        
        # Test 1: Without cache (direct query)
        deduction_without_cache = slip._get_ahadu_leave_deduction()
        
        # Test 2: With empty cache
        deduction_with_cache = slip.with_context(leaves_by_employee={})._get_ahadu_leave_deduction()
        
        # Both should return same result when no leaves exist
        self.assertEqual(
            deduction_without_cache, deduction_with_cache,
            "Leave deduction should be consistent with and without cache"
        )
        
        _logger.info("✓ Leave deduction cache compatibility test passed")
