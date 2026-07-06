/** @odoo-module **/
import { Component, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";

/**
 * Blank action shown when only the Ahadu HR Root group is granted.
 * Prevents Odoo from auto-redirecting to the first visible child action.
 */
class AhaduHrHomeAction extends Component {
    static template = xml`
        <div class="o_action" style="height:100%;"/>
    `;
    static props = ["*"];
}

registry.category("actions").add("ahadu_hr.home_action", AhaduHrHomeAction);
