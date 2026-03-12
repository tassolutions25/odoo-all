/** @odoo-module **/

import { Component } from "@odoo/owl";

export class KpiCard extends Component {
    static template = "ahadu_attendance.KpiCard";
    static props = {
        name: { type: String },
        value: { type: Number },
        onClick: { type: Function, optional: true },
    };
}
