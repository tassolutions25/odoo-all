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
            # {
            #     "keywords": [
            #         "org chart",
            #         "organization chart",
            #         "hierarchy",
            #         "employee structure",
            #     ],
            #     "response": "Opening the Employee Organization Chart.",
            #     "action": self._get_client_action(
            #         "ahadu_hr.organization_chart", "Organization Chart"
            #     ),
            # },
            {
                "keywords": ["structural chart", "department structure", "unit chart", "org chart",
                    "organization chart",
                    "hierarchy",
                    "employee structure"],
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

        # Fallback if no exact dictionary match found: search custom addons dynamically
        custom_modules = [
            'ahadu_attendance', 'ahadu_bot', 'ahadu_custom_theme', 'ahadu_elearning', 
            'ahadu_hr', 'ahadu_hr_leave', 'ahadu_hr_self_service', 'ahadu_on_duty', 
            'ahadu_payroll', 'ahadu_recruitment', 'ahadu_theme', 'ahadu_website_custom', 
            'payroll', 'payroll_account'
        ]

        if any(word in msg_lower for word in ['what can you do', 'list modules', 'features', 'help me']):
            module_names = []
            modules = request.env['ir.module.module'].sudo().search([('name', 'in', custom_modules), ('state', '=', 'installed')])
            for mod in modules:
                module_names.append(mod.shortdesc)
            return {
                "text": "I can help you with the following custom functionalities: " + ", ".join(module_names) + ". Just tell me what you want to open or do!",
                "type": "bot"
            }

        stop_words = {'to', 'the', 'a', 'an', 'is', 'are', 'i', 'want', 'open', 'show', 'me', 'please', 'can', 'you', 'my', 'create', 'new', 'for', 'in', 'of', 'and', 'or', 'do', 'any', 'anything'}
        words = [w for w in re.findall(r'\b\w+\b', msg_lower) if w not in stop_words]

        if not words:
            return {
                "text": "I only handle functionalities related to our custom modules. Please specify what you want to do (e.g., 'open attendance', 'payroll').",
                "type": "bot",
            }

        action_data = request.env['ir.model.data'].sudo().search([
            ('module', 'in', custom_modules),
            ('model', 'in', ['ir.actions.act_window', 'ir.actions.client'])
        ])

        action_ids_by_model = {
            'ir.actions.act_window': [],
            'ir.actions.client': []
        }
        for data in action_data:
            if data.model in action_ids_by_model:
                action_ids_by_model[data.model].append(data.res_id)

        windows = request.env['ir.actions.act_window'].sudo().browse(action_ids_by_model['ir.actions.act_window'])
        clients = request.env['ir.actions.client'].sudo().browse(action_ids_by_model['ir.actions.client'])

        best_action = None
        max_score = 0
        action_type = None

        for act in windows:
            score = sum(1 for w in words if re.search(r"\b" + re.escape(w) + r"\b", (act.name or '').lower()))
            if score > max_score:
                max_score = score
                best_action = act
                action_type = 'ir.actions.act_window'

        for act in clients:
            score = sum(1 for w in words if re.search(r"\b" + re.escape(w) + r"\b", (act.name or '').lower()))
            if score > max_score:
                max_score = score
                best_action = act
                action_type = 'ir.actions.client'

        if best_action and max_score > 0:
            action_dict = best_action.read()[0]
            # Ensure proper dictionary format for Odoo JS client
            action_dict['id'] = best_action.id
            if 'create' in msg_lower or 'new' in msg_lower or 'add' in msg_lower:
                if action_type == 'ir.actions.act_window':
                    action_dict['views'] = [[False, 'form']]
                    action_dict['target'] = 'current'
                    return {
                        "text": f"Ready to create a new record in {best_action.name}. Opening form.",
                        "type": "bot",
                        "action": action_dict
                    }

            return {
                "text": f"I found what you're looking for! Opening {best_action.name}.",
                "type": "bot",
                "action": action_dict
            }

        return {
            "text": "I could not find a match for that within our custom modules. Try asking for something like 'attendance', 'leave', or 'payroll'.",
            "type": "bot",
        }
