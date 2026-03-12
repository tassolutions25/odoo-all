/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class StructuralOrgChartNode extends Component {
  static template = "ahadu_hr.StructuralOrgChart.Node";
  static components = { StructuralOrgChartNode };
  static props = ["node", "onToggle"];
}

class StructuralOrgChart extends Component {
  setup() {
    this.orm = useService("orm");
    this.state = useState({
      hierarchyData: [],
      loading: true,
    });

    onWillStart(async () => {
      await this.fetchChartData();
    });
  }

  async fetchChartData() {
    this.state.loading = true;
    try {
      const data = await this.orm.call(
        "hr.department",
        "get_structural_hierarchy"
      );
      this.state.hierarchyData = data.hierarchy;
    } catch (e) {
      console.error("Failed to load structural chart data:", e);
      this.state.hierarchyData = [];
    } finally {
      this.state.loading = false;
    }
  }

  toggleNode(node) {
    if ("is_expanded" in node) {
      node.is_expanded = !node.is_expanded;
    }
  }
}

StructuralOrgChart.template = "ahadu_hr.StructuralOrgChart";
StructuralOrgChart.components = { StructuralOrgChartNode };

registry
  .category("actions")
  .add("ahadu_hr.structural_org_chart", StructuralOrgChart);
