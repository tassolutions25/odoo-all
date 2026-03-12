/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class HRAnalyticsDashboard extends Component {
  static template = "ahadu_hr.HRAnalyticsDashboard";

  setup() {
    this.orm = useService("orm");
    this.state = useState({
      loading: true,
      data: {
        vacancy_stats: {},
        span_of_control_stats: {},
      },
    });

    onWillStart(async () => {
      await this.fetchAnalyticsData();
    });
  }

  async fetchAnalyticsData() {
    this.state.loading = true;
    try {
      const result = await this.orm.call(
        "hr.employee",
        "get_hr_analytics_data"
      );
      this.state.data = result;
    } catch (error) {
      console.error("Error fetching HR analytics data:", error);
    } finally {
      this.state.loading = false;
    }
  }
}

registry
  .category("actions")
  .add("ahadu_hr.analytics_dashboard", HRAnalyticsDashboard);
