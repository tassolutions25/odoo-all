{
    "name": "Ahadu ERP Smart Assistant",
    "version": "18.0.1.0.0",
    "summary": "Free built-in chatbot dictionary for Ahadu employees and HR admins.",
    "author": "Ahadu ERP Team",
    "depends": [
        "base",
        "web",
        "mail",
        "hr",
        "ahadu_hr",
        "ahadu_hr_leave",
        "ahadu_hr_self_service",
        "ahadu_payroll",
    ],
    "data": [],
    "assets": {
        "web.assets_backend": [
            "ahadu_bot/static/src/components/ahadu_bot.scss",
            "ahadu_bot/static/src/components/ahadu_bot.xml",
            "ahadu_bot/static/src/components/ahadu_bot.js",
        ],
    },
    "installable": True,
    "application": True,
    "license": "LGPL-3",
}
