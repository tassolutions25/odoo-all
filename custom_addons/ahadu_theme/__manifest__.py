{
    'name': "ahadu_theme",

    'summary': "Customize Odoo theme colors",

    'description': """
     Customize Odoo theme colors
    """,

    "author": "Ahadu Bank DevTeam",
    'license': 'OPL-1',
    'category': 'Theme',
    'version': '0.1',
    'depends': ['base','base_setup','web'],

    'data': [
        # 'security/ir.model.access.csv',
    
        'views/res_config_settings_views.xml',
        'views/webclient_templates_right.xml',
        'views/webclient_templates_left.xml',
        'views/webclient_templates_middle.xml',
        'views/header.xml',
        
    ],
    'demo': [
        'demo/demo.xml',
    ],
    # 'images': ['static/description/banner.png'],
    'assets': {
    'web.assets_backend': [
        'ahadu_theme/static/css/custom_navbar.css',
    ],
 },
 'installable': True,
 'auto_install': False,
 'application': True,
}

