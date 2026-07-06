from odoo import models, fields, api, _
from odoo.exceptions import AccessError


class ResUsers(models.Model):
    _inherit = "res.users"

    _GROUP_MAPPING = {
        'has_menu_ahadu_hr_root': 'ahadu_hr.group_menu_ahadu_hr_root',
        'has_menu_ahadu_hr_reporting_dashboard': 'ahadu_hr.group_menu_ahadu_hr_reporting_dashboard',
        'has_menu_employee_list_ahadu': 'ahadu_hr.group_menu_employee_list_ahadu',
        'has_menu_ahadu_employee_list': 'ahadu_hr.group_menu_ahadu_employee_list',
        'has_menu_ahadu_contracts': 'ahadu_hr.group_menu_ahadu_contracts',
        'has_menu_hr_employee_mass_update': 'ahadu_hr.group_menu_hr_employee_mass_update',
        'has_menu_employee_activities': 'ahadu_hr.group_menu_employee_activities',
        'has_menu_ahadu_departments': 'ahadu_hr.group_menu_ahadu_departments',
        'has_menu_ahadu_onboarding_root': 'ahadu_hr.group_menu_ahadu_onboarding_root',
        'has_menu_employee_onboarding_all': 'ahadu_hr.group_menu_employee_onboarding_all',
        'has_menu_employee_onboarding_completed': 'ahadu_hr.group_menu_employee_onboarding_completed',
        'has_menu_employee_onboarding_pending': 'ahadu_hr.group_menu_employee_onboarding_pending',
        'has_menu_employee_onboarding_not_started': 'ahadu_hr.group_menu_employee_onboarding_not_started',
        'has_menu_employee_onboarding_requests': 'ahadu_hr.group_menu_employee_onboarding_requests',
        'has_menu_hr_structural_org_chart': 'ahadu_hr.group_menu_hr_structural_org_chart',
        'has_menu_employee_headcount_report': 'ahadu_hr.group_menu_employee_headcount_report',
        'has_menu_hr_analytics_dashboard': 'ahadu_hr.group_menu_hr_analytics_dashboard',
        'has_menu_ahadu_reporting': 'ahadu_hr.group_menu_ahadu_reporting',
        'has_menu_hr_work_location': 'ahadu_hr.group_menu_hr_work_location',
        'has_menu_hr_departure_reasons': 'ahadu_hr.group_menu_hr_departure_reasons',
        'has_menu_hr_category': 'ahadu_hr.group_menu_hr_category',
        'has_menu_hr_resume_type_menu': 'ahadu_hr.group_menu_hr_resume_type_menu',
        'has_menu_hr_grade': 'ahadu_hr.group_menu_hr_grade',
        'has_menu_hr_district': 'ahadu_hr.group_menu_hr_district',
        'has_menu_hr_region': 'ahadu_hr.group_menu_hr_region',
        'has_menu_hr_branch': 'ahadu_hr.group_menu_hr_branch',
        'has_menu_hr_city': 'ahadu_hr.group_menu_hr_city',
        'has_menu_hr_division': 'ahadu_hr.group_menu_hr_division',
        'has_menu_hr_cost_center': 'ahadu_hr.group_menu_hr_cost_center',
        'has_menu_hr_employee_type': 'ahadu_hr.group_menu_hr_employee_type',
        'has_menu_hr_hardship_allowance_level': 'ahadu_hr.group_menu_hr_hardship_allowance_level',
        'has_menu_hr_job_position': 'ahadu_hr.group_menu_hr_job_position',
        'has_menu_hr_contract_type_action': 'ahadu_hr.group_menu_hr_contract_type_action',
        'has_menu_hr_skill_type_menu': 'ahadu_hr.group_menu_hr_skill_type_menu',
        'has_menu_hr_working_time': 'ahadu_hr.group_menu_hr_working_time',
        'has_menu_hr_organogram_structure': 'ahadu_hr.group_menu_hr_organogram_structure',
        'has_menu_hr_approval_policy': 'ahadu_hr.group_menu_hr_approval_policy',
        'has_menu_hr_activity_card_access': 'ahadu_hr.group_menu_hr_activity_card_access',
        'has_menu_employee_probation': 'ahadu_hr.group_menu_employee_probation',
    }

    # -------------------------------------------------------------------------
    # Helper: sync a SINGLE group for a SINGLE field using the ORM cache
    # This avoids triggering _compute_menu_groups for all 39 fields, which would
    # overwrite the pending (dirty) value the user just set.
    # -------------------------------------------------------------------------
    def _sync_single_group(self, field_name):
        xml_id = self._GROUP_MAPPING.get(field_name)
        if not xml_id:
            return
        group = self.env.ref(xml_id, raise_if_not_found=False)
        if not group:
            return
        field_obj = self._fields[field_name]
        for user in self:
            # Read the pending value from the ORM cache directly —
            # avoids re-triggering _compute_menu_groups which would read
            # groups_id (unchanged yet) and overwrite the dirty True/False.
            try:
                val = self.env.cache.get(user, field_obj)
            except Exception:
                val = group in user.sudo().groups_id
            current = user.sudo().groups_id
            if val and group not in current:
                user.sudo().write({'groups_id': [(4, group.id)]})
            elif not val and group in current:
                user.sudo().write({'groups_id': [(3, group.id)]})

    # -------------------------------------------------------------------------
    # Shared compute: derives each boolean from groups_id membership
    # -------------------------------------------------------------------------
    @api.depends('groups_id')
    def _compute_menu_groups(self):
        for user in self:
            for field, xml_id in self._GROUP_MAPPING.items():
                group = self.env.ref(xml_id, raise_if_not_found=False)
                user[field] = group in user.groups_id if group else False

    # -------------------------------------------------------------------------
    # Field definitions — each field has its OWN inverse so the ORM only calls
    # that one method when that one checkbox is toggled, never reading the other
    # 38 fields and therefore never re-triggering _compute_menu_groups.
    # -------------------------------------------------------------------------
    has_menu_ahadu_hr_root = fields.Boolean(
        string="Ahadu HR Root",
        compute="_compute_menu_groups", inverse="_inv_ahadu_hr_root")

    has_menu_ahadu_hr_reporting_dashboard = fields.Boolean(
        string="HR Dashboard",
        compute="_compute_menu_groups", inverse="_inv_ahadu_hr_reporting_dashboard")

    has_menu_employee_list_ahadu = fields.Boolean(
        string="Employees (Parent)",
        compute="_compute_menu_groups", inverse="_inv_employee_list_ahadu")

    has_menu_ahadu_employee_list = fields.Boolean(
        string="Employees",
        compute="_compute_menu_groups", inverse="_inv_ahadu_employee_list")

    has_menu_ahadu_contracts = fields.Boolean(
        string="Contracts",
        compute="_compute_menu_groups", inverse="_inv_ahadu_contracts")

    has_menu_hr_employee_mass_update = fields.Boolean(
        string="Mass Update Employee Data",
        compute="_compute_menu_groups", inverse="_inv_hr_employee_mass_update")

    has_menu_employee_activities = fields.Boolean(
        string="Employee Activities",
        compute="_compute_menu_groups", inverse="_inv_employee_activities")

    has_menu_ahadu_departments = fields.Boolean(
        string="Departments",
        compute="_compute_menu_groups", inverse="_inv_ahadu_departments")

    has_menu_ahadu_onboarding_root = fields.Boolean(
        string="Onboarding Tracking (Parent)",
        compute="_compute_menu_groups", inverse="_inv_ahadu_onboarding_root")

    has_menu_employee_onboarding_all = fields.Boolean(
        string="Onboarding Dashboard",
        compute="_compute_menu_groups", inverse="_inv_employee_onboarding_all")

    has_menu_employee_onboarding_completed = fields.Boolean(
        string="Onboarded Employees",
        compute="_compute_menu_groups", inverse="_inv_employee_onboarding_completed")

    has_menu_employee_onboarding_pending = fields.Boolean(
        string="Pending Onboarding",
        compute="_compute_menu_groups", inverse="_inv_employee_onboarding_pending")

    has_menu_employee_onboarding_not_started = fields.Boolean(
        string="Not Onboarded",
        compute="_compute_menu_groups", inverse="_inv_employee_onboarding_not_started")

    has_menu_employee_onboarding_requests = fields.Boolean(
        string="Onboarding Requests",
        compute="_compute_menu_groups", inverse="_inv_employee_onboarding_requests")

    has_menu_hr_structural_org_chart = fields.Boolean(
        string="Structural Chart",
        compute="_compute_menu_groups", inverse="_inv_hr_structural_org_chart")

    has_menu_employee_headcount_report = fields.Boolean(
        string="Headcount Analysis",
        compute="_compute_menu_groups", inverse="_inv_employee_headcount_report")

    has_menu_hr_analytics_dashboard = fields.Boolean(
        string="Analytics Dashboard",
        compute="_compute_menu_groups", inverse="_inv_hr_analytics_dashboard")

    has_menu_ahadu_reporting = fields.Boolean(
        string="Skill Reporting",
        compute="_compute_menu_groups", inverse="_inv_ahadu_reporting")

    has_menu_hr_work_location = fields.Boolean(
        string="Work Locations",
        compute="_compute_menu_groups", inverse="_inv_hr_work_location")

    has_menu_hr_departure_reasons = fields.Boolean(
        string="Departure Reasons",
        compute="_compute_menu_groups", inverse="_inv_hr_departure_reasons")

    has_menu_hr_category = fields.Boolean(
        string="Tags",
        compute="_compute_menu_groups", inverse="_inv_hr_category")

    has_menu_hr_resume_type_menu = fields.Boolean(
        string="Resume Line Types",
        compute="_compute_menu_groups", inverse="_inv_hr_resume_type_menu")

    has_menu_hr_grade = fields.Boolean(
        string="Grades",
        compute="_compute_menu_groups", inverse="_inv_hr_grade")

    has_menu_hr_district = fields.Boolean(
        string="Districts",
        compute="_compute_menu_groups", inverse="_inv_hr_district")

    has_menu_hr_region = fields.Boolean(
        string="Regions",
        compute="_compute_menu_groups", inverse="_inv_hr_region")

    has_menu_hr_branch = fields.Boolean(
        string="Branches",
        compute="_compute_menu_groups", inverse="_inv_hr_branch")

    has_menu_hr_city = fields.Boolean(
        string="Cities",
        compute="_compute_menu_groups", inverse="_inv_hr_city")

    has_menu_hr_division = fields.Boolean(
        string="Divisions",
        compute="_compute_menu_groups", inverse="_inv_hr_division")

    has_menu_hr_cost_center = fields.Boolean(
        string="Cost Centers",
        compute="_compute_menu_groups", inverse="_inv_hr_cost_center")

    has_menu_hr_employee_type = fields.Boolean(
        string="Employee Type",
        compute="_compute_menu_groups", inverse="_inv_hr_employee_type")

    has_menu_hr_hardship_allowance_level = fields.Boolean(
        string="Hardship Allowance",
        compute="_compute_menu_groups", inverse="_inv_hr_hardship_allowance_level")

    has_menu_hr_job_position = fields.Boolean(
        string="Job Positions",
        compute="_compute_menu_groups", inverse="_inv_hr_job_position")

    has_menu_hr_contract_type_action = fields.Boolean(
        string="Employment Types",
        compute="_compute_menu_groups", inverse="_inv_hr_contract_type_action")

    has_menu_hr_skill_type_menu = fields.Boolean(
        string="Skill Types",
        compute="_compute_menu_groups", inverse="_inv_hr_skill_type_menu")

    has_menu_hr_working_time = fields.Boolean(
        string="Working Schedules",
        compute="_compute_menu_groups", inverse="_inv_hr_working_time")

    has_menu_hr_organogram_structure = fields.Boolean(
        string="Organogram Structure",
        compute="_compute_menu_groups", inverse="_inv_hr_organogram_structure")

    has_menu_hr_approval_policy = fields.Boolean(
        string="Approval Workflows",
        compute="_compute_menu_groups", inverse="_inv_hr_approval_policy")

    has_menu_hr_activity_card_access = fields.Boolean(
        string="Activity Card Access",
        compute="_compute_menu_groups", inverse="_inv_hr_activity_card_access")

    has_menu_employee_probation = fields.Boolean(
        string="Probation Reviews",
        compute="_compute_menu_groups", inverse="_inv_employee_probation")

    # -------------------------------------------------------------------------
    # Individual inverse methods — one per field so only ONE group is touched
    # per checkbox toggle; no cross-field side effects.
    # -------------------------------------------------------------------------
    def _inv_ahadu_hr_root(self):                   self._sync_single_group('has_menu_ahadu_hr_root')
    def _inv_ahadu_hr_reporting_dashboard(self):    self._sync_single_group('has_menu_ahadu_hr_reporting_dashboard')
    def _inv_employee_list_ahadu(self):             self._sync_single_group('has_menu_employee_list_ahadu')
    def _inv_ahadu_employee_list(self):             self._sync_single_group('has_menu_ahadu_employee_list')
    def _inv_ahadu_contracts(self):                 self._sync_single_group('has_menu_ahadu_contracts')
    def _inv_hr_employee_mass_update(self):         self._sync_single_group('has_menu_hr_employee_mass_update')
    def _inv_employee_activities(self):             self._sync_single_group('has_menu_employee_activities')
    def _inv_ahadu_departments(self):               self._sync_single_group('has_menu_ahadu_departments')
    def _inv_ahadu_onboarding_root(self):           self._sync_single_group('has_menu_ahadu_onboarding_root')
    def _inv_employee_onboarding_all(self):         self._sync_single_group('has_menu_employee_onboarding_all')
    def _inv_employee_onboarding_completed(self):   self._sync_single_group('has_menu_employee_onboarding_completed')
    def _inv_employee_onboarding_pending(self):     self._sync_single_group('has_menu_employee_onboarding_pending')
    def _inv_employee_onboarding_not_started(self): self._sync_single_group('has_menu_employee_onboarding_not_started')
    def _inv_employee_onboarding_requests(self):    self._sync_single_group('has_menu_employee_onboarding_requests')
    def _inv_hr_structural_org_chart(self):         self._sync_single_group('has_menu_hr_structural_org_chart')
    def _inv_employee_headcount_report(self):       self._sync_single_group('has_menu_employee_headcount_report')
    def _inv_hr_analytics_dashboard(self):          self._sync_single_group('has_menu_hr_analytics_dashboard')
    def _inv_ahadu_reporting(self):                 self._sync_single_group('has_menu_ahadu_reporting')
    def _inv_hr_work_location(self):                self._sync_single_group('has_menu_hr_work_location')
    def _inv_hr_departure_reasons(self):            self._sync_single_group('has_menu_hr_departure_reasons')
    def _inv_hr_category(self):                     self._sync_single_group('has_menu_hr_category')
    def _inv_hr_resume_type_menu(self):             self._sync_single_group('has_menu_hr_resume_type_menu')
    def _inv_hr_grade(self):                        self._sync_single_group('has_menu_hr_grade')
    def _inv_hr_district(self):                     self._sync_single_group('has_menu_hr_district')
    def _inv_hr_region(self):                       self._sync_single_group('has_menu_hr_region')
    def _inv_hr_branch(self):                       self._sync_single_group('has_menu_hr_branch')
    def _inv_hr_city(self):                         self._sync_single_group('has_menu_hr_city')
    def _inv_hr_division(self):                     self._sync_single_group('has_menu_hr_division')
    def _inv_hr_cost_center(self):                  self._sync_single_group('has_menu_hr_cost_center')
    def _inv_hr_employee_type(self):                self._sync_single_group('has_menu_hr_employee_type')
    def _inv_hr_hardship_allowance_level(self):     self._sync_single_group('has_menu_hr_hardship_allowance_level')
    def _inv_hr_job_position(self):                 self._sync_single_group('has_menu_hr_job_position')
    def _inv_hr_contract_type_action(self):         self._sync_single_group('has_menu_hr_contract_type_action')
    def _inv_hr_skill_type_menu(self):              self._sync_single_group('has_menu_hr_skill_type_menu')
    def _inv_hr_working_time(self):                 self._sync_single_group('has_menu_hr_working_time')
    def _inv_hr_organogram_structure(self):         self._sync_single_group('has_menu_hr_organogram_structure')
    def _inv_hr_approval_policy(self):              self._sync_single_group('has_menu_hr_approval_policy')
    def _inv_hr_activity_card_access(self):         self._sync_single_group('has_menu_hr_activity_card_access')
    def _inv_employee_probation(self):              self._sync_single_group('has_menu_employee_probation')

    # -------------------------------------------------------------------------
    # Select All field
    # -------------------------------------------------------------------------
    has_menu_select_all = fields.Boolean(
        string="Select All Menu Access",
        compute="_compute_select_all",
        inverse="_inverse_select_all",
    )

    @api.depends('groups_id')
    def _compute_select_all(self):
        for user in self:
            user.has_menu_select_all = all(
                self.env.ref(xml_id, raise_if_not_found=False) in user.groups_id
                for xml_id in self._GROUP_MAPPING.values()
                if self.env.ref(xml_id, raise_if_not_found=False)
            )

    def _inverse_select_all(self):
        field_obj = self._fields['has_menu_select_all']
        for user in self:
            try:
                val = self.env.cache.get(user, field_obj)
            except Exception:
                val = False
            group_ids = [
                g.id
                for xml_id in self._GROUP_MAPPING.values()
                for g in [self.env.ref(xml_id, raise_if_not_found=False)]
                if g
            ]
            if val:
                user.sudo().write({'groups_id': [(4, gid) for gid in group_ids]})
            else:
                user.sudo().write({'groups_id': [(3, gid) for gid in group_ids]})

    # -------------------------------------------------------------------------
    # Credentials check — block suspended employees
    # -------------------------------------------------------------------------
    @api.model
    def _check_credentials(self, password, user_agent_env):
        res = super()._check_credentials(password, user_agent_env)
        user = self.env.user
        if user.employee_id and user.employee_id.ahadu_state == "suspended":
            raise AccessError(
                _("Your account is currently suspended. Please contact the HR department.")
            )
        return res
