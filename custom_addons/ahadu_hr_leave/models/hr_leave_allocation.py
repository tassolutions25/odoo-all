from odoo import models, fields, api, _
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)

class HrLeaveAllocation(models.Model):
    _inherit = 'hr.leave.allocation'

     # --- ADD THIS NEW FIELD ---
    is_pro_rata_allocation = fields.Boolean(
        string="Is Pro-Rata Allocation",
        default=False,
        copy=False,
        readonly=True,
        help="This technical field marks an allocation as the automated pro-rata record for the year."
    )
    # --- END OF NEW FIELD ---

    date_of_joining = fields.Date(
        related='employee_id.date_of_joining',
        string="Employee Joining Date", store=True, readonly=True
    )
    expiry_date = fields.Date(
        string='Expiry Date', compute='_compute_expiry_date', store=True, readonly=True
    )
    expired_leaves = fields.Float(
        string="Expired Leaves", readonly=True, default=0.0,
        help="The number of leaves that were forfeited after the expiry date."
    )

    effective_remaining_leaves = fields.Float(
        string="Days Remaining", # Use the clearer label directly
        compute='_compute_effective_remaining_leaves',
        store=True,
        readonly=True,
    )

    def _manual_recompute_balance(self):
        """Helper method to manually force the calculation and writing of the effective balance."""
        _logger.info(f"Manually recomputing balance for {len(self)} allocation(s)...")
        for allocation in self:
            # The simple, correct formula: Remaining = Granted - Taken - Expired
            new_balance = allocation.number_of_days - allocation.leaves_taken - allocation.expired_leaves
            allocation.write({'effective_remaining_leaves': new_balance})
        _logger.info("Manual re-computation finished.")

    @api.depends('number_of_days', 'leaves_taken', 'expired_leaves')
    def _compute_effective_remaining_leaves(self):
        """
        This calculation is now simple and direct:
        Remaining = Total Granted - Total Taken - Total Expired
        """
        for allocation in self:
            allocation.effective_remaining_leaves = allocation.number_of_days - allocation.leaves_taken - allocation.expired_leaves
    

    @api.depends('date_from')
    def _compute_expiry_date(self):
        for allocation in self:
            if allocation.date_from:
                allocation.expiry_date = allocation.date_from + relativedelta(months=24)
            else:
                allocation.expiry_date = False

    def name_get(self):
        """
        Overrides the default display name for leave allocations to show a more
        informative label in dropdowns, including the real-time balance.
        """
        result = []
        for allocation in self:
            # For our custom annual leave, create the detailed name
            if 'Annual Leave' in allocation.name:
                name = f"{allocation.name} ({allocation.effective_remaining_leaves:.2f} / {allocation.number_of_days:.2f} days available)"
            else:
                # For other types like Paternity, Marriage, etc., show a simpler version
                name = f"{allocation.holiday_status_id.name} ({allocation.effective_remaining_leaves:.2f} days available)"
            result.append((allocation.id, name))
        return result

    # def _recompute_effective_balance(self):
    #     """ A helper method to calculate and write the effective balance. """
    #     for allocation in self:
    #         # The 'remaining_leaves' field from the base module IS available here for direct computation
    #         new_balance = allocation.number_of_days_display  - allocation.expired_leaves
    #         # We write directly to the stored field
    #         allocation.write({'effective_remaining_leaves': new_balance})

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to initialize the effective balance."""
        records = super(HrLeaveAllocation, self).create(vals_list)
        # records._manual_recompute_balance()
        records._compute_effective_remaining_leaves()
        return records

    # def write(self, vals):
    #     """Override write to recompute the balance if relevant fields change."""
    #     res = super().write(vals)
    #     if 'number_of_days' in vals or 'expired_leaves' in vals:
    #         # self._manual_recompute_balance()
    #         self._compute_effective_remaining_leaves()
    #     return res

    @api.model
    def _cron_expire_old_allocations(self):
        # ... (This method is fine, but we will make it recompute the balance)
        _logger.info("Starting cron job for leave expiry...")
        today = fields.Date.today()
        expired_allocations = self.search([
            ('state', '=', 'validate'),
            ('expiry_date', '<', today),
            ('expired_leaves', '=', 0),
            ('number_of_days_display', '>', 0)
        ])
        for alloc in expired_allocations:
            remaining_before_expiry = alloc.number_of_days_display
            alloc.write({
                'expired_leaves': remaining_before_expiry
            })
            alloc.message_post(
                body=_(
                    "<strong>%.2f days</strong> have expired from this allocation as of %s."
                ) % (remaining_before_expiry, today)
            )
            _logger.info(f"Expired {remaining_before_expiry} days for allocation {alloc.name} (ID: {alloc.id})")
        # After expiring, recompute the balance for all affected allocations
        if expired_allocations:
            expired_allocations._manual_recompute_balance()
        _logger.info("Leave expiry cron job finished.")