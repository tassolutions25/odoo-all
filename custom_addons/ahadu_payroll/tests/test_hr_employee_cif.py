from odoo.tests.common import TransactionCase

class TestHrEmployeeCIF(TransactionCase):

    def setUp(self):
        super(TestHrEmployeeCIF, self).setUp()
        self.Employee = self.env['hr.employee']

    def test_cif_extraction_from_bank_account(self):
        """Test extraction of CIF from 13-digit salary account."""
        employee = self.Employee.create({
            'name': 'Test Employee CIF Extraction',
        })
        self.env['hr.employee.bank.account'].create({
            'employee_id': employee.id,
            'account_number': '0000021412345',
            'account_type': 'salary',
        })
        
        cif = employee._extract_cif_from_salary_account()
        self.assertEqual(cif, "214", "CIF should be extracted by dropping last 5 digits and stripping leading zeros.")

    def test_cif_field_default_value(self):
        """Test the default value of the cif field."""
        employee = self.Employee.create({
            'name': 'Test Employee Default CIF'
        })
        # If it's a Char field, it should be False/None by default in Odoo OR explicitly False
        self.assertFalse(employee.cif, "CIF field should be False or empty if not set.")

    def test_cron_fetch_cif(self):
        """Test that the cron job updates CIF for employees missing it."""
        employee = self.Employee.create({
            'name': 'Test Employee Cron CIF',
        })
        self.env['hr.employee.bank.account'].create({
            'employee_id': employee.id,
            'account_number': '0000021410101',
            'account_type': 'salary',
        })
        
        self.Employee.cron_fetch_cif()
        self.assertEqual(employee.cif, "214", "Cron should have updated the CIF field.")
