# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ResUsers(models.Model):
    _inherit = 'res.users'

    ahadu_payroll_role = fields.Selection([
        ('branch_officer', 'Branch Payroll Officer'),
        ('branch_manager', 'Branch Payroll Manager'),
        ('ho_officer', 'Head Office Payroll Officer'),
        ('ho_manager', 'Head Office Payroll Manager'),
    ], string='Ahadu Payroll Role', help="Select the access level for Ahadu Payroll.")

    @api.model_create_multi
    def create(self, vals_list):
        users = super(ResUsers, self).create(vals_list)
        for user in users:
            if user.ahadu_payroll_role:
                user._update_payroll_groups(user.ahadu_payroll_role)
        return users

    def write(self, vals):
        res = super(ResUsers, self).write(vals)
        if 'ahadu_payroll_role' in vals:
            for user in self:
                user._update_payroll_groups(vals.get('ahadu_payroll_role'))
        return res

    def _update_payroll_groups(self, role):
        """
        Sync the selected Role with the underlying Res Groups.
        """
        self.ensure_one()
        
        # Define Group XML IDs (External IDs)
        # Note: We must use the full xml_id if possibly loaded from data
        # 'ahadu_payroll.group_...' 
        
        group_map = {
            'branch_officer': 'ahadu_payroll.group_branch_payroll',
            'branch_manager': 'ahadu_payroll.group_branch_payroll_manager',
            'ho_officer':     'ahadu_payroll.group_head_office_payroll_officer',
            'ho_manager':     'ahadu_payroll.group_head_office_payroll',
        }

        # List of all managed payroll groups to clear first
        # Includes Standard Payroll groups to avoid conflicts (Ahadu Role wins)
        all_managed_groups = [
            'ahadu_payroll.group_branch_payroll',
            'ahadu_payroll.group_branch_payroll_manager',
            'ahadu_payroll.group_head_office_payroll_officer',
            'ahadu_payroll.group_head_office_payroll',
            'payroll.group_payroll_user',
            'payroll.group_payroll_manager'
        ]

        # 1. Clear existing payroll groups
        # We need to get the IDs from xml_ids
        groups_to_remove = []
        for xml_id in all_managed_groups:
            group = self.env.ref(xml_id, raise_if_not_found=False)
            if group:
                groups_to_remove.append(group.id)
        
        if groups_to_remove:
            self.sudo().write({'groups_id': [(3, gid) for gid in groups_to_remove]})

        # 2. Add new groups if role is selected
        if role and role in group_map:
            groups_to_add = []
            
            # A. Add the Ahadu Specific Group
            target_xml_id = group_map[role]
            target_group = self.env.ref(target_xml_id, raise_if_not_found=False)
            if target_group:
                groups_to_add.append(target_group.id)
            
            # B. Add the Standard Odoo Payroll Group
            # Officer Roles -> Officer Group
            # Manager Roles -> Administrator Group
            standard_group_xml_id = False
            if role in ['branch_officer', 'ho_officer']:
                standard_group_xml_id = 'payroll.group_payroll_user'
            elif role in ['branch_manager', 'ho_manager']:
                standard_group_xml_id = 'payroll.group_payroll_manager'
            
            if standard_group_xml_id:
                std_group = self.env.ref(standard_group_xml_id, raise_if_not_found=False)
                if std_group:
                    groups_to_add.append(std_group.id)
            
            if groups_to_add:
                self.sudo().write({'groups_id': [(4, gid) for gid in groups_to_add]})

    @api.onchange('ahadu_payroll_role')
    def _onchange_ahadu_payroll_role(self):
        # This is for UI immediate feedback if needed, basically a stub
        pass
