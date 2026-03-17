from odoo import http
from odoo.http import request
import re


class AhaduBotController(http.Controller):

    def _get_window_action(self, name, res_model):
        """Helper to generate a window action dictionary for HR Models"""
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": res_model,
            "view_mode": "list,form",
            "views": [[False, "list"], [False, "form"]],
            "target": "current",
        }

    def _get_client_action(self, tag, name):
        """Helper to generate a client action for Custom Dashboards"""
        return {
            "type": "ir.actions.client",
            "name": name,
            "tag": tag,
        }

    @http.route("/ahadu_bot/chat", type="json", auth="user")
    def process_chat(self, message):
        msg_lower = message.lower()

        # ==========================================
        # THE FULL AHADU ERP DICTIONARY
        # ==========================================
        intents = [
            # --- 1. GREETINGS & HELP ---
            {
                "keywords": ["hello", "hi", "hey", "help", "who are you"],
                "response": "Hello! I am your Ahadu ERP Assistant. I can help you request leaves, view payslips, open HR dashboards, or handle employee activities like promotions and transfers. What do you need?",
            },
            # --- 2. EMPLOYEE SELF-SERVICE ---
            {
                "keywords": [
                    "onboard",
                    "onboarding",
                    "join",
                    "new employee profile",
                    "my profile",
                ],
                "response": "Welcome to Ahadu! I am opening the self-service portal so you can complete your onboarding profile.",
                "url": "/my/onboarding",
            },
            {
                "keywords": [
                    "document",
                    "id card",
                    "id renewal",
                    "experience letter",
                    "permanency letter",
                    "request letter",
                ],
                "response": "You can request HR documents right here. I'm opening the Document Request portal for you.",
                "url": "/my/document_request",
            },
            {
                "keywords": [
                    "self service",
                    "my dashboard",
                    "employee dashboard",
                    "portal",
                ],
                "response": "Taking you to your Employee Self-Service Dashboard.",
                "url": "/my/dashboard",
            },
            # --- 3. LEAVE & TIME OFF ---
            {
                "keywords": [
                    "request leave",
                    "time off",
                    "vacation",
                    "sick leave",
                    "maternity",
                    "paternity",
                    "apply leave",
                ],
                "response": "I can help with that. I am opening the Leave Request window for you.",
                "action": {
                    "type": "ir.actions.act_window",
                    "name": "New Leave Request",
                    "res_model": "ahadu.leave.request.wizard",
                    "view_mode": "form",
                    "target": "new",
                },
            },
            {
                "keywords": [
                    "leave balance",
                    "remaining leave",
                    "how many days off",
                    "my allocation",
                ],
                "response": "Here are your leave balances and allocations.",
                "action": self._get_window_action(
                    "My Allocations", "hr.leave.allocation"
                ),
            },
            {
                "keywords": [
                    "leave report",
                    "leave audit",
                    "leave analytics",
                    "manager efficiency",
                ],
                "response": "Opening the comprehensive Leave Reports Wizard.",
                "action": {
                    "type": "ir.actions.act_window",
                    "name": "Leave Master Reports",
                    "res_model": "ahadu.leave.report.wizard",
                    "view_mode": "form",
                    "target": "new",
                },
            },
            # --- 4. PAYROLL & BENEFITS ---
            {
                "keywords": ["my payslip", "payslips", "salary slip", "pay slip"],
                "response": "Here are your payslips.",
                "action": self._get_window_action("My Payslips", "hr.payslip"),
            },
            {
                "keywords": ["payroll batch", "payslip run", "generate payroll"],
                "response": "Opening the Payroll Batches (Payslip Runs) window for HR Admins.",
                "action": self._get_window_action("Payslip Batches", "hr.payslip.run"),
            },
            {
                "keywords": [
                    "loan",
                    "salary advance",
                    "borrow money",
                    "emergency loan",
                ],
                "response": "Here is the Employee Loans section.",
                "action": self._get_window_action("Employee Loans", "hr.loan"),
            },
            {
                "keywords": ["overtime", "extra hours", "ot tracking"],
                "response": "Opening the Overtime Tracking interface.",
                "action": self._get_window_action(
                    "Overtime Tracking", "ahadu.overtime.tracking"
                ),
            },
            {
                "keywords": ["cash indemnity", "indemnity tracking", "cia"],
                "response": "Opening Cash Indemnity Tracking.",
                "action": self._get_window_action(
                    "Cash Indemnity Tracking", "cash.indemnity.tracking"
                ),
            },
            # --- 5. HR ADMIN ACTIVITIES (Promotions, Transfers, etc.) ---
            {
                "keywords": ["promote", "promotion", "promotions"],
                "response": "Opening the Employee Promotions window.",
                "action": self._get_window_action(
                    "Employee Promotions", "hr.employee.promotion"
                ),
            },
            {
                "keywords": ["demote", "demotion", "demotions"],
                "response": "Opening the Employee Demotions window.",
                "action": self._get_window_action(
                    "Employee Demotions", "hr.employee.demotion"
                ),
            },
            {
                "keywords": ["transfer", "change branch", "move location"],
                "response": "Opening the Employee Transfers window.",
                "action": self._get_window_action(
                    "Employee Transfers", "hr.employee.transfer"
                ),
            },
            {
                "keywords": ["terminate", "termination", "fire", "resign", "layoff"],
                "response": "Opening the Employee Terminations window.",
                "action": self._get_window_action(
                    "Employee Terminations", "hr.employee.termination"
                ),
            },
            {
                "keywords": ["acting", "acting assignment"],
                "response": "Opening Acting Assignments.",
                "action": self._get_window_action(
                    "Acting Assignments", "hr.employee.acting"
                ),
            },
            {
                "keywords": ["temporary assignment", "temp assign"],
                "response": "Opening Temporary Assignments.",
                "action": self._get_window_action(
                    "Temporary Assignments", "hr.employee.temporary.assignment"
                ),
            },
            {
                "keywords": [
                    "disciplinary",
                    "warning",
                    "suspension",
                    "penalty",
                    "violation",
                ],
                "response": "Opening the Disciplinary Actions window.",
                "action": self._get_window_action(
                    "Disciplinary Actions", "hr.employee.disciplinary"
                ),
            },
            {
                "keywords": ["guarantee", "guarantor"],
                "response": "Opening Employee Guarantees.",
                "action": self._get_window_action(
                    "Employee Guarantees", "hr.employee.guarantee"
                ),
            },
            {
                "keywords": ["retire", "retirement"],
                "response": "Opening the Employee Retirements window.",
                "action": self._get_window_action(
                    "Employee Retirements", "hr.employee.retirement"
                ),
            },
            {
                "keywords": ["ctc", "salary adjustment", "adjust salary"],
                "response": "Opening CTC (Salary) Adjustments.",
                "action": self._get_window_action("CTC Adjustments", "hr.employee.ctc"),
            },
            # --- 6. DASHBOARDS & ANALYTICS ---
            {
                "keywords": [
                    "hr analytics",
                    "vacancy analysis",
                    "span of control",
                    "manager ratio",
                ],
                "response": "Opening the HR Analytics Dashboard.",
                "action": self._get_client_action(
                    "ahadu_hr.analytics_dashboard", "HR Analytics Dashboard"
                ),
            },
            {
                "keywords": [
                    "hr reporting",
                    "employee dashboard",
                    "hr dashboard",
                    "headcount",
                ],
                "response": "Opening the main HR Reporting Dashboard.",
                "action": self._get_client_action(
                    "ahadu_hr.reporting_dashboard", "HR Reporting Dashboard"
                ),
            },
            {
                "keywords": [
                    "org chart",
                    "organization chart",
                    "hierarchy",
                    "employee structure",
                ],
                "response": "Opening the Employee Organization Chart.",
                "action": self._get_client_action(
                    "ahadu_hr.organization_chart", "Organization Chart"
                ),
            },
            {
                "keywords": ["structural chart", "department structure", "unit chart"],
                "response": "Opening the Structural Organization Chart.",
                "action": self._get_client_action(
                    "ahadu_hr.structural_org_chart", "Structural Org Chart"
                ),
            },
        ]

        # ==========================================
        # MATCHING LOGIC
        # ==========================================
        for intent in intents:
            for keyword in intent["keywords"]:
                # re.search looks for the keyword anywhere in the user's sentence
                if re.search(r"\b" + re.escape(keyword) + r"\b", msg_lower):

                    response_data = {"text": intent["response"], "type": "bot"}

                    # Attach action or url if it exists in the dictionary
                    if "action" in intent:
                        response_data["action"] = intent["action"]
                    if "url" in intent:
                        response_data["url"] = intent["url"]

                    return response_data

        # Fallback if the bot doesn't understand the question
        return {
            "text": "I'm sorry, I didn't quite catch that. Try asking me for 'leave', 'payslip', 'promotions', 'org chart', or 'HR dashboard'.",
            "type": "bot",
        }
