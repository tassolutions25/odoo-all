# -*- coding: utf-8 -*-
from odoo import models, api

class HrLeave(models.Model):
    _inherit = 'hr.leave'

    def action_approve(self):
        """
        Override to automatically handle retroactive leave approvals.
        """
        # First, call the original Odoo approval logic
        res = super().action_approve()

        # Now, run our custom logic for the leaves that were just approved
        for leave in self.filtered(lambda l: l.state == 'validate'):
            # Find any 'Unplanned Absence' records that fall within this leave's date range
            absences_to_excuse = self.env['ab.hr.unplanned.absence'].search([
                ('employee_id', '=', leave.employee_id.id),
                ('date', '>=', leave.date_from.date()),
                ('date', '<=', leave.date_to.date()),
                ('state', 'in', ['detected', 'confirmed']), # Only update non-excused absences
            ])
            
            if absences_to_excuse:
                # Mark these absences as 'Excused' and log a note
                absences_to_excuse.write({
                    'state': 'excused',
                    'notes': f"Automatically excused due to approved Time Off request: {leave.display_name}"
                })
        
        return res