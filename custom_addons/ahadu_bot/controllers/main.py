from odoo import http
from odoo.http import request
import re


class AhaduBotController(http.Controller):

    @http.route("/ahadu_bot/chat", type="json", auth="user")
    def process_chat(self, message):
        """Processes the employee's message and returns a response and optional action."""
        msg_lower = message.lower()

        # Define Intents based on Ahadu's specific modules and actions
        intents = [
            {
                "keywords": ["leave", "time off", "vacation", "sick", "absence"],
                "response": "I can help with that! Opening the Leave Request wizard for you.",
                "action_id": "ahadu_hr_leave.action_ahadu_leave_request_wizard",
            },
            {
                "keywords": ["onboard", "onboarding", "join", "new employee"],
                "response": "Welcome! You can complete your onboarding profile on the self-service portal. I'll take you there now.",
                "url": "/my/onboarding",
            },
            {
                "keywords": [
                    "document",
                    "letter",
                    "id renewal",
                    "experience",
                    "guarantee",
                ],
                "response": "You can request documents like Experience Letters or ID Renewals through the portal.",
                "url": "/my/document_request",
            },
            {
                "keywords": ["payslip", "salary", "pay", "earnings"],
                "response": "Here are your payslips.",
                "action_id": "hr_payroll.action_view_hr_payslip_form",  # Standard Odoo payslip action
            },
            {
                "keywords": ["report", "leave balance", "balance", "audit"],
                "response": "Opening the Comprehensive Leave Report Wizard.",
                "action_id": "ahadu_hr_leave.action_ahadu_leave_report_wizard",
            },
            {
                "keywords": ["overtime", "extra hours"],
                "response": "Let's open your overtime tracking.",
                "action_id": "ahadu_payroll.action_ahadu_overtime_tracking",
            },
            {
                "keywords": ["dashboard", "home", "main"],
                "response": "Taking you to the Self Service Dashboard.",
                "url": "/my/dashboard",
            },
        ]

        # Match Intent
        for intent in intents:
            for keyword in intent["keywords"]:
                if re.search(r"\b" + re.escape(keyword) + r"\b", msg_lower):

                    response_data = {"text": intent["response"], "type": "bot"}

                    # Fetch the Odoo Window Action if specified
                    if intent.get("action_id"):
                        try:
                            action = request.env["ir.actions.act_window"]._for_xml_id(
                                intent["action_id"]
                            )
                            response_data["action"] = action
                        except Exception as e:
                            response_data["text"] = (
                                f"I found what you need, but you might not have access to it. ({str(e)})"
                            )

                    # Fetch the URL redirect if specified
                    if intent.get("url"):
                        response_data["url"] = intent["url"]

                    return response_data

        # Fallback response if no intent is matched
        return {
            "text": "I'm your Ahadu ERP Assistant. You can ask me to request leave, show your payslips, apply for documents, or complete your onboarding!",
            "type": "bot",
        }
