# -*- coding: utf-8 -*-
{
    'name': "Ahadu Bank Attendance Management",
    'summary': "Advanced attendance management system for Ahadu Bank.",
    'description': """
        - Multi-method attendance tracking (Biometric, PC, Mobile, Card).
        - Shift and Overtime Management workflows.
        - Integration with Time Off to block check-ins on leave days.
        - Custom reports and security groups for banking operations.
    """,
    'author': "ERP team",
    'website': "https://www.yourcompany.com",
    'category': 'Human Resources/Attendances',
    'version': '18.0.1.0.0',
    'depends': [
        'base',
        'base_setup',
        'hr',
        'ahadu_hr',
        'hr_attendance',
        'hr_holidays', # Dependency for Time Off integration 
        'mail', 
        'resource',
        'web',
        'payroll',
    ],
    'data': [
        # Security files must be loaded first
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/ir_cron_data.xml',
        'data/email_template_data.xml',
        # 'data/biotime_cron.xml',
        'data/hr_salary_rule_data.xml',#new

        # 'views/hr_employee_views.xml',
        
        # 'views/hr_contract_views.xml', # New
        'wizards/attendance_report_wizard_views.xml',
        'wizards/shift_mass_schedule_wizard_views.xml',

        'views/hr_resource_calendar_views.xml',
        'views/hr_attendance_policy_views.xml', # <-- ACTION IS DEFINED HERE
        'views/hr_attendance_policy_allocation_views.xml',
        'views/ab_hr_attendance_views.xml',
        'views/res_config_settings_views.xml',
        'views/ab_hr_unplanned_absence_views.xml',
        'views/ab_hr_attendance_sheet_views.xml',
        'views/ab_hr_disciplinary_note_views.xml',
        'views/ab_hr_duty_request_views.xml',
        'views/ab_hr_overtime_policy_views.xml', 
        'views/ab_hr_attendance_lateness_reason_views.xml',
        'views/ab_attendance_dashboard_views.xml',

        # 'views/biotime_integration_views.xml',
        'views/ab_hr_shift_type_views.xml', 
        'views/ab_hr_shift_schedule_views.xml', 
        'views/ab_hr_shift_swap_views.xml',
        'views/ab_hr_overtime_request_views.xml', # Modified
        'views/ahadu_attendance_menus.xml',

         # Reports
        'reports/ab_attendance_reports.xml',
        'reports/ab_attendance_report_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # Be very specific with the path to your component files
             # 1. Load the Chart.js library first
            'ahadu_attendance/static/src/libs/chart.js/chart.umd.js',

            # 2. Load our custom components
            'ahadu_attendance/static/src/components/chart_renderer/kpi_card.js',
            'ahadu_attendance/static/src/components/chart_renderer/kpi_card.xml',
            'ahadu_attendance/static/src/components/chart_renderer/kpi_card.scss',
            'ahadu_attendance/static/src/components/chart_renderer/chart_renderer.js',
            'ahadu_attendance/static/src/components/chart_renderer/chart_renderer.xml',
            
            # 3. Load the dashboard itself last
            'ahadu_attendance/static/src/components/dashboard/attendance_dashboard.js',
            'ahadu_attendance/static/src/components/dashboard/attendance_dashboard.xml',
            'ahadu_attendance/static/src/components/dashboard/attendance_dashboard.scss',
            'ahadu_attendance/static/src/css/ot_request.scss',
        ],
    },
    'external_dependencies': {'python': ['requests']},
    'installable': True,
    'application': True, # Mark this as a main application
    'license': 'LGPL-3',
}