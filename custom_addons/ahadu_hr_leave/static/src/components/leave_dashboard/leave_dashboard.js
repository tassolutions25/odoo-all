/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";

export class AhaduLeaveDashboard extends Component {
    static template = "ahadu_hr_leave.LeaveDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        // Get the dashboard_id from the action's params
        this.dashboardId = this.props.action.params.dashboard_id;

        this.dashboardData = useState({
            balance_cards: [],
            nav_cards: [],
        });

        onWillStart(async () => {
            const data = await this.orm.call(
                "ahadu.hr.leave.dashboard",
                "get_dashboard_data",
                [this.dashboardId] // Pass the ID
            );
            this.dashboardData.balance_cards = data.balance_cards;
            this.dashboardData.nav_cards = data.nav_cards;
        });
    }

    onNavCardClick(actionName) {
        // Call the 'call_action' method on our specific dashboard record
        this.orm.call("ahadu.hr.leave.dashboard", "call_action", [[this.dashboardId], actionName]).then((action) => {
            if (action) {
                this.action.doAction(action);
            }
        });
    }
}

registry.category("actions").add("ahadu_leave_dashboard_tag", AhaduLeaveDashboard);