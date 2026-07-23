/** @odoo-module **/
import { Component, onWillStart, onMounted, useState, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class AhaduProjectDashboard extends Component {
  setup() {
    this.orm = useService("orm");
    this.action = useService("action");
    this.state = useState({
      activeRole: "executive",
      isPmoAdmin: false,
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
        overdue_tasks: 0,
        open_risks: 0,
        critical_issues: 0,
        pending_changes: 0,
        success_rate: 100.0,
        delayed_projects: 0,
        resource_utilization: 0,
        my_tasks_count: 0,
        my_overdue_tasks: 0,
        my_completed_tasks: 0,
        my_projects: 0,
        timesheet_hours: 0,
        schedule_performance: 100.0,
        programs_count: 0,
        compliance_rate: 100.0,
        wbs_completion: 0,
        open_issues: 0,
      },
      charts: {},
      tables: {
        pending_approvals: [],
        strategic_milestones: [],
        high_risks: [],
        critical_issues: [],
        my_tasks: [],
        delayed_projects: [],
        resource_summary: [],
        project_list: [],
        my_projects_detail: [],
        change_requests: [],
      },
      filters: {
        active_role: "auto",
        project_id: "all",
        program_id: "all",
        department_id: "all",
        division_id: "all",
        sponsor_id: "all",
        pm_id: "all",
        category_id: "all",
        state: "all",
        priority: "all",
        risk_level: "all",
        resource_id: "all",
        budget_status: "all",
        health: "all",
        date_from: "",
        date_to: "",
      },
      lookup: {
        projects: [],
        programs: [],
        departments: [],
        divisions: [],
        sponsors: [],
        pms: [],
        categories: [],
        resources: [],
      },
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
      "#27ae60",
      "#f39c12",
    ];

    // Chart canvas refs — one unique ref per canvas element across all tabs
    this.chartRefs = {
      // Executive
      exec_health: useRef("exec_health"),
      exec_byDept: useRef("exec_byDept"),
      exec_byCategory: useRef("exec_byCategory"),
      exec_bySponsor: useRef("exec_bySponsor"),
      exec_budgetByDept: useRef("exec_budgetByDept"),
      exec_budgetVariance: useRef("exec_budgetVariance"),
      // Sponsor
      sponsor_health: useRef("sponsor_health"),
      sponsor_budgetUtil: useRef("sponsor_budgetUtil"),
      sponsor_schedPerf: useRef("sponsor_schedPerf"),
      // PMO
      pmo_byDivision: useRef("pmo_byDivision"),
      pmo_budgetByDept: useRef("pmo_budgetByDept"),
      pmo_riskByLevel: useRef("pmo_riskByLevel"),
      pmo_schedPerf: useRef("pmo_schedPerf"),
      pmo_byCategory: useRef("pmo_byCategory"),
      // Division (EPAD)
      div_health: useRef("div_health"),
      div_byCategory: useRef("div_byCategory"),
      div_wbsProgress: useRef("div_wbsProgress"),
      div_budgetVar: useRef("div_budgetVar"),
      // PM
      pm_taskStatus: useRef("pm_taskStatus"),
      pm_budgetUtil: useRef("pm_budgetUtil"),
      pm_riskLevel: useRef("pm_riskLevel"),
      pm_schedPerf: useRef("pm_schedPerf"),
      pm_milestoneProg: useRef("pm_milestoneProg"),
      // Team
      team_taskProgress: useRef("team_taskProgress"),
      team_timesheetHrs: useRef("team_timesheetHrs"),
    };

    onWillStart(async () => {
      await this.fetchDashboardData();
    });

    onMounted(() => {
      setTimeout(() => {
        this.renderCharts();
      }, 200);
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
      if (data) {
        if (data.user_role) {
          this.state.activeRole = data.user_role;
          // Only override if PMO admin is switching roles
          if (this.state.isPmoAdmin && this.state.filters.active_role && this.state.filters.active_role !== "auto") {
            this.state.activeRole = this.state.filters.active_role;
          }
        }
        if (data.is_pmo_admin !== undefined) {
          this.state.isPmoAdmin = data.is_pmo_admin;
        }
        if (data.kpis) Object.assign(this.state.kpis, data.kpis);
        if (data.charts) this.state.charts = data.charts;
        if (data.tables) Object.assign(this.state.tables, data.tables);
        if (data.filters_lookup) this.state.lookup = data.filters_lookup;
      }
    } catch (error) {
      console.error("Error fetching dashboard data:", error);
      this.state.error = "Dashboard data could not be loaded. Please check your permissions or contact your administrator.";
    } finally {
      this.state.loading = false;
    }
  }

  async onFilterChange(ev) {
    const target = ev.target;
    const name = target.name;
    const value = target.value;
    this.state.filters[name] = value;
    if (name === "active_role" && this.state.isPmoAdmin) {
      this.state.activeRole = value;
    }
    await this.fetchDashboardData();
    setTimeout(() => this.renderCharts(), 200);
  }

  async onRoleSwitch(role) {
    if (!this.state.isPmoAdmin) return;
    this.state.activeRole = role;
    this.state.filters.active_role = role;
    await this.fetchDashboardData();
    setTimeout(() => this.renderCharts(), 200);
  }

  renderCharts() {
    if (this.state.loading) return;
    this.destroyCharts();
    const role = this.state.activeRole;
    const charts = this.state.charts;

    if (role === "executive") {
      this._renderDoughnutChart("exec_health", this.chartRefs.exec_health.el, charts.by_health, "Portfolio Health");
      this._renderBarChart("exec_byDept", this.chartRefs.exec_byDept.el, charts.by_department, "Projects by Directorate", true);
      this._renderPieChart("exec_byCategory", this.chartRefs.exec_byCategory.el, charts.by_category, "By Category");
      this._renderBarChart("exec_bySponsor", this.chartRefs.exec_bySponsor.el, charts.by_sponsor, "By Sponsor", true);
      this._renderGroupedBarChart("exec_budgetByDept", this.chartRefs.exec_budgetByDept.el, charts.budget_by_dept);
      this._renderVarianceBarChart("exec_budgetVariance", this.chartRefs.exec_budgetVariance.el, charts.budget_variance);
    } else if (role === "sponsor") {
      this._renderDoughnutChart("sponsor_health", this.chartRefs.sponsor_health.el, charts.by_health, "Sponsored Portfolio Health");
      this._renderGroupedBarChart("sponsor_budgetUtil", this.chartRefs.sponsor_budgetUtil.el, charts.budget_by_dept);
      this._renderBarChart("sponsor_schedPerf", this.chartRefs.sponsor_schedPerf.el, charts.schedule_performance, "Schedule Performance", false);
    } else if (role === "pmo") {
      this._renderBarChart("pmo_byDivision", this.chartRefs.pmo_byDivision.el, charts.by_division, "Projects by Division", true);
      this._renderGroupedBarChart("pmo_budgetByDept", this.chartRefs.pmo_budgetByDept.el, charts.budget_by_dept);
      this._renderDoughnutChart("pmo_riskByLevel", this.chartRefs.pmo_riskByLevel.el, charts.risk_by_level, "Risk by Level");
      this._renderBarChart("pmo_schedPerf", this.chartRefs.pmo_schedPerf.el, charts.schedule_performance, "Schedule Performance", false);
      this._renderPieChart("pmo_byCategory", this.chartRefs.pmo_byCategory.el, charts.by_category, "By Category");
    } else if (role === "division") {
      this._renderDoughnutChart("div_health", this.chartRefs.div_health.el, charts.by_health, "Portfolio Health");
      this._renderPieChart("div_byCategory", this.chartRefs.div_byCategory.el, charts.by_category, "By Category");
      this._renderBarChart("div_wbsProgress", this.chartRefs.div_wbsProgress.el, charts.wbs_progress, "WBS Progress %", false);
      this._renderVarianceBarChart("div_budgetVar", this.chartRefs.div_budgetVar.el, charts.budget_variance);
    } else if (role === "pm") {
      this._renderDoughnutChart("pm_taskStatus", this.chartRefs.pm_taskStatus.el, charts.task_status, "Task Status");
      this._renderGroupedBarChart("pm_budgetUtil", this.chartRefs.pm_budgetUtil.el, charts.budget_by_dept);
      this._renderDoughnutChart("pm_riskLevel", this.chartRefs.pm_riskLevel.el, charts.risk_by_level, "Risk by Level");
      this._renderBarChart("pm_schedPerf", this.chartRefs.pm_schedPerf.el, charts.schedule_performance, "Schedule Performance", false);
      this._renderBarChart("pm_milestoneProg", this.chartRefs.pm_milestoneProg.el, charts.milestone_progress, "Milestone Completion", false);
    } else if (role === "team") {
      this._renderDoughnutChart("team_taskProgress", this.chartRefs.team_taskProgress.el, charts.task_status, "My Task Status");
      this._renderBarChart("team_timesheetHrs", this.chartRefs.team_timesheetHrs.el, charts.timesheet_hours, "Timesheet Hours by Week", false);
    }
  }

  _renderChart(type, chartId, canvas, chartData, title, options = {}) {
    if (!canvas || !chartData || !chartData.labels || !chartData.data || !chartData.labels.length) return;
    try {
      const ctx = canvas.getContext("2d");
      const baseOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "bottom", labels: { font: { size: 11 }, usePointStyle: true, padding: 12 } },
          tooltip: { backgroundColor: "rgba(0,0,0,0.8)", titleColor: "#fff", bodyColor: "#fff" },
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
            borderWidth: type === "bar" ? 0 : 2,
            borderRadius: type === "bar" ? 4 : 0,
          }],
        },
        options: { ...baseOptions, ...options },
      });
    } catch (e) {
      console.error(`Error rendering chart ${chartId}:`, e);
    }
  }

  _renderDoughnutChart(id, el, data, title) {
    this._renderChart("doughnut", id, el, data, title, { cutout: "60%" });
  }

  _renderPieChart(id, el, data, title) {
    this._renderChart("pie", id, el, data, title);
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

  _renderGroupedBarChart(id, canvas, data) {
    if (!canvas || !data || !data.labels || !data.labels.length) return;
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
          plugins: { legend: { position: "top" } },
          scales: {
            x: { grid: { color: "rgba(0,0,0,0.05)" } },
            y: {
              beginAtZero: true,
              ticks: { callback: (v) => v >= 1000000 ? (v / 1000000).toFixed(1) + "M" : (v / 1000).toFixed(0) + "K" },
            },
          },
        },
      });
    } catch (e) {
      console.error("Error rendering grouped bar chart:", e);
    }
  }

  _renderVarianceBarChart(id, canvas, data) {
    if (!canvas || !data || !data.labels || !data.labels.length) return;
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
          plugins: { legend: { display: false } },
          scales: {
            x: { grid: { display: false } },
            y: { ticks: { callback: (v) => v >= 1000000 ? (v / 1000000).toFixed(1) + "M" : (v / 1000).toFixed(0) + "K" } },
          },
        },
      });
    } catch (e) {
      console.error("Error rendering variance chart:", e);
    }
  }

  destroyCharts() {
    Object.values(this.charts).forEach((chart) => {
      if (chart && typeof chart.destroy === "function") {
        try { chart.destroy(); } catch (e) { console.warn("Error destroying chart:", e); }
      }
    });
    this.charts = {};
  }

  openRecord(model, id) {
    this.action.doAction({
      type: "ir.actions.act_window",
      res_model: model,
      res_id: id,
      views: [[false, "form"]],
      target: "current",
    });
  }

  openFilteredList(model, domain, title) {
    this.action.doAction({
      name: title,
      type: "ir.actions.act_window",
      res_model: model,
      domain: domain,
      views: [[false, "list"], [false, "form"]],
      target: "current",
    });
  }

  formatCurrency(val) {
    if (!val && val !== 0) return "0";
    if (val >= 1000000) return (val / 1000000).toFixed(2) + "M ETB";
    if (val >= 1000) return (val / 1000).toFixed(1) + "K ETB";
    return val.toFixed(0) + " ETB";
  }

  formatPercent(val) {
    if (!val && val !== 0) return "0%";
    return parseFloat(val).toFixed(1) + "%";
  }

  getHealthBadge(health) {
    const map = { green: "success", amber: "warning", red: "danger" };
    return map[health] || "secondary";
  }

  getStateBadge(state) {
    const map = { draft: "secondary", submitted: "info", approved: "primary", active: "success", closed: "dark", cancelled: "danger" };
    return map[state] || "secondary";
  }
}

AhaduProjectDashboard.template = "ahadu_project_management.ProjectDashboard";
registry.category("actions").add("ahadu_project_management.project_dashboard", AhaduProjectDashboard);
