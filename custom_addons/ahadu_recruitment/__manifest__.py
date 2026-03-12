{
    'name': 'Ahadu Recruitment',
    'version': '1.0',
    'category': 'Human Resources',
    'summary': 'Custom Recruitment Module inheriting Odoo\'s default',
    'description': """
        This module inherits and extends the default Odoo Recruitment module,
        providing the same core functionality and allowing for future
        customizations specific to Ahadu's needs.
    """,
    'author': 'Your Name',
    'website': '',
    'depends': [
        'base',
        'hr',
        'hr_recruitment',
        'hr_contract',
        'utm',
        'hr_skills',
        'website',], # This is crucial for inheriting
    'data': [
        'security/ir.model.access.csv',
        'views/recruitment_views_inherit.xml',
        'views/menu_views.xml',
        'views/hr_job_views.xml',
        'views/hr_applicant_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}