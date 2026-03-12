/** @odoo-module **/

import { Component, onMounted, onWillUpdateProps, onWillUnmount, useRef } from "@odoo/owl";

// REMOVED THE IMPORT for chart.umd.js from here.
// We will rely on it being loaded globally via the manifest.

export class ChartRenderer extends Component {
    static template = "ahadu_attendance.ChartRenderer";
    static props = {
        type: { type: String },
        data: { type: Object },
    };

    setup() {
        this.chart = null;
        this.canvasRef = useRef("canvas");

        onMounted(() => this.renderChart());
        onWillUpdateProps((nextProps) => this.renderChart(nextProps));
        onWillUnmount(() => {
            if (this.chart) {
                this.chart.destroy();
            }
        });
    }

    renderChart(props = this.props) {
        if (this.chart) {
            this.chart.destroy();
        }
        // THIS IS THE FIX: Access Chart from the global 'window' object.
        if (this.canvasRef.el && window.Chart) {
            this.chart = new window.Chart(this.canvasRef.el, {
                type: props.type,
                data: props.data,
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                },
            });
        }
    }
}