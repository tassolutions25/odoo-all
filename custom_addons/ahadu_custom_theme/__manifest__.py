{
    'name': 'Ahadu Custom Theme',
    'version': '1.1',
    'author': 'Software Development Team',
    'category': 'Theme',
    'license': 'LGPL-3',  
    'summary': 'Customize Odoo theme colors',
    'depends': ['web', 'ahadu_hr', 'ahadu_theme', 'auth_signup', 'website'],
    'data': [
        'data/data.xml',
        'views/login.xml',
        'views/signup.xml',
        'views/reset_password.xml',
        'views/header.xml',
        'views/background_layout.xml',         
    ],
    'assets': {

        'web.assets_frontend': [
            'ahadu_custom_theme/static/src/img/favicon.ico',
            'ahadu_custom_theme/static/src/css/login.css',
        ],
        
        'web._assets_primary_variables': [
            'ahadu_custom_theme/static/src/scss/primary_variables.scss', 
        ],
            
       
    },
    'installable': True,
    'application': True,

}
