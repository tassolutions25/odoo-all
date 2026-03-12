{
    'name': 'Ahadu eLearning',
    'version': '1.0',
    'category': 'Website/eLearning',
    'summary': 'Customizations for Odoo 18 eLearning',
    'description': """
        This module provides customizations for the Odoo 18 eLearning (website_slides) module.
    """,
    'author': 'Ahadu ',
    'website': 'https://www.ahadu.com',
    'depends': ['website_slides'],
    'data': [
        'security/ir.model.access.csv',
        'views/assets.xml',
        'views/slide_channel_views.xml',
        'views/slide_slide_views.xml',
        'views/slide_tag_views.xml',
        'views/slide_question_views.xml',
        'views/menus.xml',
        'data/ir_config_parameter_data.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
