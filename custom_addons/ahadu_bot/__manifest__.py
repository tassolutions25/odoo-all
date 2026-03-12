{
    "name": "Ahadu ERP Assistant Bot",
    "version": "18.0.1.0.0",
    # 'category': 'Human Resources',
    "summary": "AI Assistant to help employees navigate the Ahadu ERP system.",
    "author": "ERP Team",
    "depends": [
        "base",
        "web",
        "mail",
        "ahadu_hr",
        "ahadu_hr_leave",
        "ahadu_hr_self_service",
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
