{
    'name': "Custom_Job_Application",
    'summary': "Adds custom fields to the job application form and applicant backend.",
    'description': """
        This module extends the Odoo Recruitment module to include additional fields
        on the job application form and displays them in the backend applicant view.
    """,
    'author': "Your Name",
    'website': "",
    'category': 'Human Resources',
    'version': '1.0',
    'depends': ['hr_recruitment', 'website_hr_recruitment', 'website', 'website_blog'],
    'data': [
        'data/ir_cron.xml',
        'views/templates.xml',
        'views/job_apply_assets.xml',
        'views/website_hr_recruitment_templates.xml',
        'views/menu_views.xml',
        'security/ir.model.access.csv',  
    ],
    # 'assets': {
    #     'web.assets_frontend': [
    #         # 'ahadu_website_custom/static/src/js/disable_apply_script.js',
    #         # 'ahadu_website_custom/static/src/js/apply_form_action_fix.js',
    #         # 'ahadu_website_custom/static/src/js/job_apply_validation.js',
    #         # 'ahadu_website_custom/static/src/js/job_form_validation.js',
    #     ],
    # },
    'installable': True,
    'application': True,
}