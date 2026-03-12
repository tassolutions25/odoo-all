{
    "name": "Ahadu Bank Payroll",
    "summary": """
        Custom payroll module for Ahadu Bank S.C.
    """,
    "author": "Ahadu Dev Team",
    "website": "https://www.ahadubank.com",
    "category": "Human Resources/Payroll",
    "version": "18.0.1.0.0",
    # any module necessary for this one to work correctly
    "depends": [
        "hr",
        "hr_contract",
        "payroll",  # This is the OCA base module
        "ahadu_hr_leave",  # Needed for leave type logic
        "ahadu_hr",  # Needed for hr.cost.center and hr.region
    ],
    # always loaded
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/account_data.xml",
        "data/salary_structure_data.xml",
        "data/ahadu_tax_data.xml",
        "data/pay_group_data.xml",
        "data/hr_contract_action_data.xml",
        # 'data/mail_template_data.xml',
        "data/api_sync_data.xml",
        "data/loan_data.xml",
        "report/ahadu_payroll_report.xml",
        "report/payslip_template.xml",
        "report/payroll_sheet_template.xml",
        "report/journal_entry_template.xml",
        "views/payroll_configuration_views.xml",
        "views/hr_loan_views.xml",
        "wizard/hr_loan_refuse_wizard_views.xml",
        "views/hr_views.xml",
        "views/payroll_dashboard_views.xml",
        "views/hr_contract_views.xml",
        "views/hr_salary_rule_views.xml",
        "views/hr_payslip_run_views.xml",
        "views/payroll_adjustment_views.xml",
        "views/hr_employee_deduction_views.xml",
        "views/ahadu_journal_entry_views.xml",
        "views/res_users_views.xml",  # New User Role View
        "views/ahadu_tax_views.xml",
        "views/ahadu_tax_config_views.xml",
        "views/ahadu_payroll_report_wizard_views.xml",
        "views/ahadu_overtime_views.xml",  # New view file (Moved here for menu parent dependency)
        "views/cash_indemnity_views.xml",  # New view file
        "views/hr_branch_mapping_views.xml",
        "views/res_config_settings_views.xml",
        "views/hr_termination_views.xml",
        "views/hr_report_views.xml",
        "views/comparative_analytics_views.xml",
        "views/ahadu_payroll_hr_employee_views.xml",
        "views/hr_employee_bank_account_views.xml",
        "data/ahadu_tax_config_data.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "ahadu_payroll/static/src/css/dashboard.css",
        ],
    },
    "installable": True,
    "application": True,  # Mark this as a main application
    "auto_install": False,
}
