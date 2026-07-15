/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
import { Component, onWillStart, useState, onMounted } from "@odoo/owl";

// Matrix logic mirroring python export logic
const INHERENT_MATRIX = {
    "1,1": "#00B050", "1,2": "#00B050", "1,3": "#92D050", "1,4": "#92D050", "1,5": "#92D050",
    "2,1": "#00B050", "2,2": "#92D050", "2,3": "#92D050", "2,4": "#FFFF00", "2,5": "#FFFF00",
    "3,1": "#92D050", "3,2": "#92D050", "3,3": "#FFFF00", "3,4": "#FFFF00", "3,5": "#FF0000",
    "4,1": "#92D050", "4,2": "#FFFF00", "4,3": "#FFFF00", "4,4": "#FF0000", "4,5": "#FF0000",
    "5,1": "#92D050", "5,2": "#FFFF00", "5,3": "#FF0000", "5,4": "#FF0000", "5,5": "#A50021"
};

const CONTROL_MATRIX = {
    "1,1": "#C00000", "1,2": "#C00000", "1,3": "#FF4B21", "1,4": "#FF4B21", "1,5": "#FF4B21",
    "2,1": "#C00000", "2,2": "#FF4B21", "2,3": "#FF4B21", "2,4": "#FFFF00", "2,5": "#FFFF00",
    "3,1": "#FF4B21", "3,2": "#FF4B21", "3,3": "#FFFF00", "3,4": "#FFFF00", "3,5": "#99FF33",
    "4,1": "#FF4B21", "4,2": "#FFFF00", "4,3": "#FFFF00", "4,4": "#99FF33", "4,5": "#99FF33",
    "5,1": "#FF4B21", "5,2": "#FFFF00", "5,3": "#99FF33", "5,4": "#99FF33", "5,5": "#009900"
};

const RESIDUAL_MATRIX = {
    "very_high,very_weak": "#B40000", "very_high,weak": "#FF0000", "very_high,moderate": "#FFFF00", "very_high,strong": "#FFFF00", "very_high,very_strong": "#92D050",
    "high,very_weak": "#FF0000", "high,weak": "#FF0000", "high,moderate": "#FFFF00", "high,strong": "#92D050", "high,very_strong": "#92D050",
    "medium,very_weak": "#FFFF00", "medium,weak": "#FFFF00", "medium,moderate": "#92D050", "medium,strong": "#92D050", "medium,very_strong": "#525252",
    "low,very_weak": "#92D050", "low,weak": "#92D050", "low,moderate": "#92D050", "low,strong": "#525252", "low,very_strong": "#525252",
    "very_low,very_weak": "#525252", "very_low,weak": "#525252", "very_low,moderate": "#525252", "very_low,strong": "#525252", "very_low,very_strong": "#525252"
};

export class RiskDashboard extends Component {
    static template = "ahadu_risk_register.RiskDashboard";

    setup() {
        this.action = useService("action");
        this.charts = {};
        this.state = useState({
            data: null,
            isLoading: true,
            filters: {
                time: 'all',
                branch: 'all',
                department: 'all',
                category: 'all',
                rating: 'all'
            }
        });

        onWillStart(async () => {
            await this.loadData();
        });

        onMounted(() => {
            this.renderCharts();
        });
    }

    async loadData() {
        try {
            const data = await rpc("/api/risk_dashboard/data", { filters: this.state.filters });
            this.state.data = data;
            this.state.isLoading = false;
        } catch (error) {
            console.error("Error loading dashboard data", error);
        }
    }

    async onFilterChange(field, ev) {
        this.state.filters[field] = ev.target.value;
        await this.loadData();
        // Wait for Owl to finish re-rendering the DOM before drawing charts
        setTimeout(() => this.renderCharts(), 50);
    }

    renderCharts() {
        if (!this.state.data) return;
        if (typeof Chart === "undefined") return;

        // Destroy existing charts
        if (this.charts) {
            Object.values(this.charts).forEach(c => {
                if (c) c.destroy();
            });
        }
        this.charts = {};

        const catEl = document.getElementById("categoryChart");
        const catData = this.state.data.category_counts;
        if (catEl) {
            this.charts.categoryChart = new Chart(catEl, {
                type: "pie",
                data: {
                    labels: Object.keys(catData),
                    datasets: [{
                        data: Object.values(catData),
                        backgroundColor: [
                            "#FF6384", "#36A2EB", "#FFCE56", "#4BC0C0", "#9966FF", "#FF9F40", "#E7E9ED", "#71B37C"
                        ]
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });
        }

        const statEl = document.getElementById("statusChart");
        const statData = this.state.data.status_counts;
        if (statEl) {
            this.charts.statusChart = new Chart(statEl, {
                type: "bar",
                data: {
                    labels: Object.keys(statData),
                    datasets: [{
                        label: "Risks by Status",
                        data: Object.values(statData),
                        backgroundColor: "#36A2EB"
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });
        }

        const branchEl = document.getElementById("branchChart");
        const branchData = this.state.data.branch_counts;
        if (branchEl) {
            this.charts.branchChart = new Chart(branchEl, {
                type: "bar",
                data: {
                    labels: Object.keys(branchData),
                    datasets: [{
                        label: "Risks per Branch",
                        data: Object.values(branchData),
                        backgroundColor: "#FFCE56"
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });
        }

        const deptEl = document.getElementById("departmentChart");
        const deptData = this.state.data.department_counts;
        if (deptEl) {
            this.charts.departmentChart = new Chart(deptEl, {
                type: "line",
                data: {
                    labels: Object.keys(deptData),
                    datasets: [{
                        label: "Risks per Department",
                        data: Object.values(deptData),
                        borderColor: "#4BC0C0",
                        fill: true,
                        backgroundColor: "rgba(75, 192, 192, 0.2)"
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });
        }
    }

    getInherentColor(l, i) {
        return INHERENT_MATRIX[`${l},${i}`] || "#FFFFFF";
    }

    getControlColor(a, e) {
        return CONTROL_MATRIX[`${a},${e}`] || "#FFFFFF";
    }

    getResidualColor(inherent_rating, control_rating) {
        return RESIDUAL_MATRIX[`${inherent_rating},${control_rating}`] || "#FFFFFF";
    }

    getRatingColor(rating) {
        const colors = {
            'very_high': '#B40000',
            'high': '#FF0000',
            'medium': '#FFFF00',
            'low': '#92D050',
            'very_low': '#525252'
        };
        return colors[rating] || "#FFFFFF";
    }

    getTextColor(bgHex) {
        const darkBgs = ["#990033", "#FF0000", "#C00000", "#109F10", "#00B050", "#1B4170", "#A50021", "#B40000", "#009900", "#DF0A0A", "#525252"];
        return darkBgs.includes(bgHex.toUpperCase()) ? "text-white" : "text-dark";
    }
}

registry.category("actions").add("ahadu_risk_register.risk_dashboard", RiskDashboard);
