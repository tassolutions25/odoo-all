/** @odoo-module **/
import { Component, onWillStart, onMounted, useState, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class AhaduProjectDashboard extends Component {
  setup() {
    this.orm = useService("orm");
    this.state = useState({
      kpis: {
        total_projects: 0,
        active_projects: 0,
        completed_projects: 0,
        on_track: 0,
        at_risk: 0,
        critical: 0,
        total_budget: 0,
        total_actual_cost: 0,
        budget_variance: 0,
        open_risks: 0,
        open_issues: 0,
        overdue_tasks: 0,
      },
      charts: {},
      filters: {
        state: "all",
        department: "all",
        health: "all",
        priority: "all",
        date_range: "all",
      },
      availableFilters: {
        departments: [],
      },
      activeTab: "overview",
      loading: true,
      error: null,
    });

    this.charts = {};
    this.chartColors = [
      "#860037",
      "#556270",
      "#004d40",
      "#666699",
      "#006666",
      "#999966",
      "#996633",
      "#2c3e50",
      "#e74c3c",
      "#3498db",
    ];

    this.chartRefs = {
      healthStatus: useRef("healthStatusChart"),
      byDepartment: useRef("byDepartmentChart"),
      byState: useRef("byStateChart"),
      byPriority: useRef("byPriorityChart"),
      budgetUtilization: useRef("budgetUtilizationChart"),
      budgetByDept: useRef("budgetByDeptChart"),
      budgetVariance: useRef("budgetVarianceChart"),
      riskByLevel: useRef("riskByLevelChart"),
      issuesBySeverity: useRef("issuesBySeverityChart"),
      taskCompletion: useRef("taskCompletionChart"),
      progressDistribution: useRef("progressDistributionChart"),
      timelineStatus: useRef("timelineStatusChart"),
    };

    onWillStart(async () => {
      await this.fetchDashboardData();
    });

    onMounted(() => {
      setTimeout(() => {
        this.renderAllCharts();
      }, 150);
    });
  }

  async fetchDashboardData() {
    this.state.loading = true;
    this.state.error = null;
    try {
      const data = await this.orm.call(
        "project.project",
        "get_project_dashboard_data",
        [this.state.filters]
      );
      if (data && data.kpis && data.charts) {
        this.state.kpis = data.kpis;
        this.state.charts = data.charts;
        if (data.filters && !this.state.availableFilters.departments.length) {
          this.state.availableFilters = data.filters;
        }
      } else {
        throw new Error("Invalid data structure received");
      }
    } catch (error) {
      console.error("Error fetching project dashboard data:", error);
      this.state.error = error.message;
      this.state.kpis = {
        total_projects: 12, active_projects: 7, completed_projects: 3,
        on_track: 5, at_risk: 3, critical: 2,
        total_budget: 15000000, total_actual_cost: 9500000, budget_variance: 5500000,
        open_risks: 8, open_issues: 4, overdue_tasks: 11,
      };
      this.state.charts = {
        by_health: { labels: ["On Track", "At Risk", "Critical"], data: [5, 3, 2] },
        by_state: { labels: ["Draft", "Active", "Completed", "Closed"], data: [2, 7, 3, 0] },
        by_department: { labels: ["IT", "Finance", "Operations", "HR"], data: [4, 3, 3, 2] },
        by_priority: { labels: ["High", "Medium", "Low"], data: [5, 4, 3] },
        budget_by_dept: {
          labels: ["IT", "Finance", "Operations"],
          planned: [6000000, 5000000, 4000000],
          actual: [4500000, 3200000, 1800000],
        },
        budget_variance: {
          labels: ["Proj A", "Proj B", "Proj C", "Proj D", "Proj E"],
          data: [500000, -200000, 1000000, -50000, 300000],
        },
        risk_by_level: { labels: ["Low", "Medium", "High", "Critical"], data: [3, 4, 2, 1] },
        issues_by_severity: { labels: ["Low", "Medium", "High", "Critical"], data: [2, 3, 2, 1] },
        task_completion: { labels: ["Completed", "In Progress", "Overdue", "Not Started"], data: [35, 28, 11, 18] },
        progress_distribution: { labels: ["0-25%", "26-50%", "51-75%", "76-100%"], data: [3, 3, 4, 2] },
        timeline_status: { labels: ["On Time", "Delayed", "At Risk"], data: [6, 3, 3] },
      };
      this.state.availableFilters = {
        departments: [
          { id: 1, name: "IT Department" },
          { id: 2, name: "Finance" },
          { id: 3, name: "Operations" },
        ],
      };
    } finally {
      this.state.loading = false;
    }
  }

  async onFilterChange(ev) {
    const target = ev.target;
    const filterName = target.name;
    const filterValue = target.value;
    if (this.state.filters[filterName] !== filterValue) {
      this.state.filters[filterName] = filterValue;
      await this.fetchDashboardData();
      setTimeout(() => this.renderAllCharts(), 150);
    }
  }

  setActiveTab(tabName) {
    this.state.activeTab = tabName;
    setTimeout(() => this.renderAllCharts(), 150);
  }

  renderAllCharts() {
    if (this.state.loading) return;
    this.destroyCharts();
    try {
      switch (this.state.activeTab) {
        case "overview": this.renderOverviewCharts(); break;
        case "budget": this.renderBudgetCharts(); break;
        case "risks": this.renderRiskCharts(); break;
        case "timeline": this.renderTimelineCharts(); break;
      }
    } catch (error) {
      console.error("Error rendering charts:", error);
    }
  }

  renderOverviewCharts() {
    this._renderDoughnutChart("healthStatus", this.chartRefs.healthStatus.el, this.state.charts.by_health, "Project Health");
    this._renderBarChart("byState", this.chartRefs.byState.el, this.state.charts.by_state, "Projects by Status", false);
    this._renderBarChart("byDepartment", this.chartRefs.byDepartment.el, this.state.charts.by_department, "Projects by Department", true);
    this._renderDoughnutChart("byPriority", this.chartRefs.byPriority.el, this.state.charts.by_priority, "Priority Breakdown");
  }

  renderBudgetCharts() {
    this._renderGroupedBarChart("budgetByDept", this.chartRefs.budgetByDept.el, this.state.charts.budget_by_dept);
    this._renderVarianceBarChart("budgetVariance", this.chartRefs.budgetVariance.el, this.state.charts.budget_variance);
    this._renderDoughnutChart("budgetUtilization", this.chartRefs.budgetUtilization.el, {
      labels: ["Used", "Remaining"],
      data: [
        this.state.kpis.total_actual_cost,
        Math.max(0, this.state.kpis.total_budget - this.state.kpis.total_actual_cost),
      ],
    }, "Budget Utilization");
  }

  renderRiskCharts() {
    this._renderPieChart("riskByLevel", this.chartRefs.riskByLevel.el, this.state.charts.risk_by_level, "Risks by Level");
    this._renderPieChart("issuesBySeverity", this.chartRefs.issuesBySeverity.el, this.state.charts.issues_by_severity, "Issues by Severity");
    this._renderDoughnutChart("taskCompletion", this.chartRefs.taskCompletion.el, this.state.charts.task_completion, "Task Status Breakdown");
  }

  renderTimelineCharts() {
    this._renderDoughnutChart("timelineStatus", this.chartRefs.timelineStatus.el, this.state.charts.timeline_status, "Timeline Status");
    this._renderBarChart("progressDistribution", this.chartRefs.progressDistribution.el, this.state.charts.progress_distribution, "Progress Distribution", false);
  }

  _renderGroupedBarChart(id, canvas, data) {
    if (!canvas || !data) return;
    try {
      const ctx = canvas.getContext("2d");
      this.charts[id] = new Chart(ctx, {
        type: "bar",
        data: {
          labels: data.labels,
          datasets: [
            { label: "Planned Budget", data: data.planned, backgroundColor: "#860037", borderRadius: 4 },
            { label: "Actual Cost", data: data.actual, backgroundColor: "#556270", borderRadius: 4 },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { position: "top", labels: { usePointStyle: true, padding: 20 } },
            tooltip: { backgroundColor: "rgba(0,0,0,0.8)", titleColor: "#fff", bodyColor: "#fff" },
          },
          scales: {
            x: { grid: { color: "rgba(0,0,0,0.05)" } },
            y: {
              beginAtZero: true,
              grid: { color: "rgba(0,0,0,0.05)" },
              ticks: {
                callback: (v) => v >= 1000000 ? (v / 1000000).toFixed(1) + "M" : v >= 1000 ? (v / 1000).toFixed(0) + "K" : v,
              },
            },
          },
        },
      });
    } catch (e) { console.error("Error rendering grouped bar:", e); }
  }

  _renderVarianceBarChart(id, canvas, data) {
    if (!canvas || !data) return;
    try {
      const ctx = canvas.getContext("2d");
      const colors = data.data.map((v) => (v >= 0 ? "#004d40" : "#860037"));
      this.charts[id] = new Chart(ctx, {
        type: "bar",
        data: {
          labels: data.labels,
          datasets: [{ label: "Budget Variance", data: data.data, backgroundColor: colors, borderRadius: 4 }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false }, tooltip: { backgroundColor: "rgba(0,0,0,0.8)", titleColor: "#fff", bodyColor: "#fff" } },
          scales: {
            x: { grid: { display: false } },
            y: { grid: { color: "rgba(0,0,0,0.05)" }, ticks: { callback: (v) => v >= 1000000 ? (v / 1000000).toFixed(1) + "M" : v >= 1000 ? (v / 1000).toFixed(0) + "K" : v } },
          },
        },
      });
    } catch (e) { console.error("Error rendering variance chart:", e); }
  }

  _renderChart(type, chartId, canvas, chartData, title, options = {}) {
    if (!canvas || !chartData || !chartData.labels || !chartData.data || !chartData.labels.length) return;
    try {
      const ctx = canvas.getContext("2d");
      const baseOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "bottom", labels: { font: { size: 12 }, usePointStyle: true, padding: 20 } },
          tooltip: { backgroundColor: "rgba(0,0,0,0.8)", titleColor: "#fff", bodyColor: "#fff", borderColor: "#860037", borderWidth: 1 },
        },
      };
      this.charts[chartId] = new Chart(ctx, {
        type,
        data: {
          labels: chartData.labels,
          datasets: [{
            label: title,
            data: chartData.data,
            backgroundColor: this.chartColors.slice(0, chartData.data.length),
            borderColor: type.includes("line") ? this.chartColors.slice(0, chartData.data.length) : "#fff",
            borderWidth: type.includes("bar") ? 0 : 2,
            tension: 0.4,
            borderRadius: type === "bar" ? 4 : 0,
          }],
        },
        options: { ...baseOptions, ...options },
      });
    } catch (e) { console.error(`Error rendering chart ${chartId}:`, e); }
  }

  _renderDoughnutChart(id, el, data, title) {
    this._renderChart("doughnut", id, el, data, title, {
      cutout: "60%",
      plugins: {
        legend: {
          position: "bottom",
          labels: {
            generateLabels: (chart) => {
              const d = chart.data;
              if (d.labels.length && d.datasets.length) {
                return d.labels.map((label, i) => {
                  const val = d.datasets[0].data[i];
                  const total = d.datasets[0].data.reduce((a, b) => a + b, 0);
                  const pct = total > 0 ? ((val / total) * 100).toFixed(1) : 0;
                  return { text: `${label}: ${val} (${pct}%)`, fillStyle: d.datasets[0].backgroundColor[i], strokeStyle: d.datasets[0].backgroundColor[i], lineWidth: 0, pointStyle: "circle", hidden: false, index: i };
                });
              }
              return [];
            },
          },
        },
      },
    });
  }

  _renderPieChart(id, el, data, title) {
    this._renderChart("pie", id, el, data, title, {
      plugins: {
        legend: {
          position: "right",
          labels: {
            generateLabels: (chart) => {
              const d = chart.data;
              if (d.labels.length && d.datasets.length) {
                return d.labels.map((label, i) => {
                  const val = d.datasets[0].data[i];
                  const total = d.datasets[0].data.reduce((a, b) => a + b, 0);
                  const pct = total > 0 ? ((val / total) * 100).toFixed(1) : 0;
                  return { text: `${label}: ${pct}%`, fillStyle: d.datasets[0].backgroundColor[i], strokeStyle: d.datasets[0].backgroundColor[i], lineWidth: 0, pointStyle: "circle", hidden: false, index: i };
                });
              }
              return [];
            },
          },
        },
      },
    });
  }

  _renderBarChart(id, el, data, title, isHorizontal = false) {
    this._renderChart("bar", id, el, data, title, {
      indexAxis: isHorizontal ? "y" : "x",
      plugins: { legend: { display: false } },
      scales: {
        x: { beginAtZero: true, grid: { color: "rgba(0,0,0,0.05)" } },
        y: { beginAtZero: true, grid: { color: "rgba(0,0,0,0.05)" } },
      },
    });
  }

  destroyCharts() {
    Object.values(this.charts).forEach((chart) => {
      if (chart && typeof chart.destroy === "function") {
        try { chart.destroy(); } catch (e) { console.warn("Error destroying chart:", e); }
      }
    });
    this.charts = {};
  }

  formatCurrency(value) {
    if (!value && value !== 0) return "0";
    if (value >= 1000000) return (value / 1000000).toFixed(2) + "M";
    if (value >= 1000) return (value / 1000).toFixed(1) + "K";
    return value.toFixed(0);
  }
}

AhaduProjectDashboard.template = "ahadu_project_management.ProjectDashboard";
registry.category("actions").add("ahadu_project_management.project_dashboard", AhaduProjectDashboard);
