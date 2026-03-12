/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class OrganizationChartNode extends Component {
  static template = "ahadu_hr.OrgChart.Node";
  static components = { OrganizationChartNode };
  static props = ["node", "onToggle"];
}

class OrganizationChart extends Component {
  setup() {
    this.orm = useService("orm");
    this.state = useState({
      hierarchyData: [],
      loading: true,
      filters: {
        department_id: "all",
        job_id: "all",
      },
      availableFilters: {
        departments: [],
        job_positions: [],
      },
    });

    onWillStart(async () => {
      await this.fetchChartData();
    });
  }

  async fetchChartData() {
    this.state.loading = true;
    try {
      const data = await this.orm.call(
        "hr.employee",
        "get_employee_hierarchy",
        [],
        { filters: this.state.filters } // Pass filters to the backend
      );
      this.state.hierarchyData = this._addExpansionState(data.hierarchy);
      if (!this.state.availableFilters.departments.length) {
        this.state.availableFilters = data.filters;
      }
    } catch (e) {
      console.error("Failed to load employee hierarchy:", e);
      this.state.hierarchyData = [];
    } finally {
      this.state.loading = false;
    }
  }

  _addExpansionState(nodes) {
    return nodes.map((node) => {
      if (node.children && node.children.length > 0) {
        node.is_expanded = false; // Start collapsed
        node.children = this._addExpansionState(node.children);
      }
      return node;
    });
  }

  toggleNode(node) {
    if ("is_expanded" in node) {
      node.is_expanded = !node.is_expanded;
    }
  }

  async onFilterChange(ev) {
    const { name, value } = ev.target;
    if (this.state.filters[name] !== value) {
      this.state.filters[name] = value;
      await this.fetchChartData();
    }
  }

  async resetFilters() {
    this.state.filters = {
      department_id: "all",
      job_id: "all",
    };
    await this.fetchChartData();
  }
}

OrganizationChart.template = "ahadu_hr.OrganizationChart";
OrganizationChart.components = { OrganizationChartNode };

registry
  .category("actions")
  .add("ahadu_hr.organization_chart", OrganizationChart);
