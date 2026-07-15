{
    "name": "Ahadu Risk Register",
    "version": "18.0.1.0.0",
    "category": "Risk Management",
    "summary": "Bank-Wide Risk Register — Risk Identification, Assessment, Scoring & Reporting",
    "description": """
        Implements the Bank-Wide Risk Register (BWRR) as specified in the
        May 2026 Business Requirements Document.

        Features:
        - Risk identification with RIN auto-generation
        - 5×5 Inherent Risk scoring (Likelihood × Impact)
        - Control Strength assessment (Adequacy × Effectiveness)
        - Residual Risk via BRD matrix lookup
        - Color-coded risk ratings (Very Low → Very High)
        - Excel export matching IBD.xlsx layout
        - QWeb PDF report with Ahadu Bank branding
        - Chatter audit trail on all critical fields
        - Role-based security (Risk Owner vs RCMD Admin)
        - Risk Guidelines & References vault
    """,
    "author": "Ahadu Bank DevTeam",
    "license": "Other proprietary",
    "depends": [
        "base",
        "mail",
        "web",
        "ahadu_hr",
    ],
    "data": [
        "security/risk_security.xml",
        "security/ir.model.access.csv",
        "data/ir_sequence_data.xml",
        "data/ir_cron_data.xml",
        "data/risk_category_data.xml",
        "data/mail_server_data.xml",
        "views/risk_register_views.xml",
        "views/risk_guideline_views.xml",
        "views/risk_mitigation_views.xml",
        "views/risk_category_views.xml",
        "wizard/risk_excel_export_views.xml",
        "report/risk_report.xml",
        "report/risk_report_templates.xml",
        "report/risk_board_report_templates.xml",
        "views/dashboard_views.xml",
        "views/menu_items.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "ahadu_risk_register/static/src/css/risk_dashboard.css",
            "ahadu_risk_register/static/src/js/risk_dashboard.js",
            "ahadu_risk_register/static/src/xml/risk_dashboard.xml",
            "ahadu_risk_register/static/src/js/hr_org_chart_patch.js",
        ],
    },
    "installable": True,
    "auto_install": False,
    "application": True,
}
