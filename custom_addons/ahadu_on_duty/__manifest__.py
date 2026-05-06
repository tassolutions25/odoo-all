# -*- coding: utf-8 -*-
{
    'name': "Ahadu On-Duty Management",
    'summary': "Advanced On-Duty request management with attendance integration for Ahadu Bank.",
    'description': """
        - Full/Half/Hourly On-Duty request workflow.
        - Multi-level approval (Manager → HR).
        - Automatic virtual attendance log creation.
        - Dashboard integration with Ahadu Attendance.
        - Payroll integration (OD hours = 100% worked).
        - Banking compliance: attachment requirements, GPS tracking.
    """,
    'author': "ERP Team",
    'website': "https://www.ahadubank.com",
    'category': 'Human Resources/Attendances',
    'version': '18.0.1.0.0',
    'depends': [
        'ahadu_attendance',
        'hr_holidays',
        'mail',
        'resource',
    ],
    'data': [
        # Security (loaded first)
        'security/security.xml',
        'security/ir.model.access.csv',

        # Data
        'data/ir_sequence_data.xml',
        'data/email_template_data.xml',

        # Views
        'views/hr_on_duty_views.xml',
        'views/hr_attendance_inherit_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
