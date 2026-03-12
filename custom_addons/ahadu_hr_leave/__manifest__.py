{
    'name': "Ahadu HR Leave",
    'version': '18.0.1.0.0',
    'summary': "Adds custom features to the Leave module.",
    'author': "Ahadu Dev Team",
    'category': 'Human Resources/Leave',
    'license': 'LGPL-3', 
    'depends': [
        'hr_holidays', 
        'web',
        'hr',
    ],
    'data': [
        # Security Rules
        'security/ir.model.access.csv',
        'security/leave_security.xml',
        # 'security/hr_holidays_security.xml',

        # Data Files
        'data/hr_leave_type_data.xml',      
        'data/ir_cron_data.xml',  
        'data/hr_leave_dashboard_data.xml',

        #  Wizards
        'wizard/report_wizards_views.xml',
        'wizard/leave_request_wizard_views.xml',
        'wizard/pro_rata_leave_wizard_views.xml',
        'wizard/leave_report_wizard_views.xml',
        # 'wizard/leave_balance_report_wizard_views.xml',
        # 'wizard/leave_ledger_report_wizard_views.xml',
        'wizard/leave_partial_cancel_wizard_views.xml',
        'wizard/leave_full_cancel_wizard_views.xml',

        #Reports
        'report/leave_balance_report.xml',
        'report/leave_report_templates.xml',
        'report/leave_ledger_report_templates.xml',

        # Views
        'views/hr_leave_views.xml',
        # 'views/hr_leave_request_views.xml',
        'views/my_time_off_views.xml',
        'views/hr_leave_form_views.xml',
        'views/hr_dashboard_views.xml',
        'views/hr_employee_views.xml',
        'views/hr_leave_allocation_views.xml',
        'views/migrated_leave_history_views.xml',
        'views/public_holiday_views.xml',
        'views/res_config_settings_views.xml',
        'views/menu_items.xml',
        
        
        # the server action file
        'data/ir_actions_server_data.xml',
        'data/ir_cron_data.xml',
    ],

    'assets': {
        'web.assets_backend': [
            # custom dashboard components
            'ahadu_hr_leave/static/src/css/dashboard.css',
            'ahadu_hr_leave/static/src/components/leave_dashboard/leave_dashboard.xml',
            'ahadu_hr_leave/static/src/components/leave_dashboard/leave_dashboard.js',
            # custom calendar components
            'ahadu_hr_leave/static/src/css/calendar_view.css',
            'ahadu_hr_leave/static/src/components/calendar_view/calendar_view.js',
            'ahadu_hr_leave/static/src/components/calendar_view/calendar_view.xml',
         

            
 
        ],
    },


    'installable': True,
    'application': True,
    'auto_install': False,
}