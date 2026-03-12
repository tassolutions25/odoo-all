/** @odoo-module **/
import { Component, onWillStart, onMounted, useState, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class AhaduHRReportingDashboard extends Component {
  setup() {
    this.orm = useService("orm");
    this.state = useState({
      kpis: {
        total_employees: 0,
        female_employees: 0,
        male_employees: 0,
        female_percentage: 0,
        male_percentage: 0,
        promotions: 0,
        transfers: 0,
        demotions: 0,
        retirements: 0,
        disciplinary: 0,
      },
      charts: {},
      filters: {
        branch: "all",
        department: "all",
        newly_joined: "all",
        gender: "all",
        age_group: "all",
        job_position: "all",
        grade: "all",
        district: "all",
      },
      availableFilters: {
        branches: [],
        departments: [],
        genders: [],
        age_groups: [],
        job_positions: [],
        grades: [],
        districts: [],
      },
      activeTab: "overview",
      loading: true,
      error: null,
    });

    this.charts = {};
    this.chartColors = [
      "#860037",
      "#556270",
      "#a7adba",
      "#004d40",
      "#666699",
      "#006666",
      "#999966",
      "#996633",
      "#d1e0e0",
      "#ddddbb",
    ];

    this.chartRefs = {
      gender: useRef("genderChart"),
      age: useRef("ageChart"),
      location: useRef("locationChart"),
      hires: useRef("hiresChart"),
      department: useRef("departmentChart"),
      grade: useRef("gradeChart"),
      district: useRef("districtChart"),
      jobPosition: useRef("jobPositionChart"), // ADDED
      positionClassification: useRef("positionClassificationChart"),
      activitySummary: useRef("activitySummaryChart"),
      activityTrends: useRef("activityTrendsChart"),
      promotionsByGrade: useRef("promotionsByGradeChart"),
      transfersByBranch: useRef("transfersByBranchChart"),
      retirementsByType: useRef("retirementsByTypeChart"),
      disciplinaryByType: useRef("disciplinaryByTypeChart"),
    };

    onWillStart(async () => {
      await this.fetchDashboardData();
    });

    onMounted(() => {
      // Small delay to ensure DOM is ready
      setTimeout(() => {
        this.renderAllCharts();
      }, 100);
    });
  }

  async fetchDashboardData() {
    this.state.loading = true;
    this.state.error = null;

    try {
      console.log("Fetching dashboard data with filters:", this.state.filters);

      const data = await this.orm.call(
        "hr.employee",
        "get_employee_dashboard_data",
        [this.state.filters]
      );

      console.log("Received dashboard data:", data);

      if (data && data.kpis && data.charts) {
        this.state.kpis = data.kpis;
        this.state.charts = data.charts;

        if (data.filters && !this.state.availableFilters.branches.length) {
          this.state.availableFilters = data.filters;
        }
      } else {
        throw new Error("Invalid data structure received");
      }
    } catch (error) {
      console.error("Error fetching dashboard data:", error);
      this.state.error = error.message;

      // Set fallback data
      this.state.kpis = {
        total_employees: 8,
        female_employees: 3,
        male_employees: 5,
        female_percentage: 37.5,
        male_percentage: 62.5,
        promotions: 2,
        transfers: 1,
        demotions: 0,
        retirements: 0,
        disciplinary: 0,
      };

      this.state.charts = {
        by_gender: { labels: ["M", "F"], data: [5, 3] },
        by_age: {
          labels: ["20-29", "30-39", "40-49", "50-59"],
          data: [2, 3, 2, 1],
        },
        by_location: {
          labels: ["Head Office", "Bole Branch", "Piazza Branch"],
          data: [4, 2, 2],
        },
        by_department: { labels: ["HR", "IT", "Finance"], data: [2, 3, 3] },
        by_grade: {
          labels: ["Level 1", "Level 2", "Level 3"],
          data: [3, 3, 2],
        },
        by_job_position: {
          // ADDED Fallback data
          labels: ["Manager", "Developer", "Analyst"],
          data: [2, 3, 3],
        },
        by_district: {
          labels: ["Addis Ababa", "Oromia", "Amhara"],
          data: [4, 2, 2],
        },
        by_position_classification: {
          labels: ["Management", "Non-Management"],
          data: [2, 6],
        },
        hires_over_time: {
          labels: [
            "Jan 2024",
            "Feb 2024",
            "Mar 2024",
            "Apr 2024",
            "May 2024",
            "Jun 2024",
          ],
          data: [1, 2, 0, 1, 3, 2],
        },
        activity_summary: {
          labels: [
            "Promotions",
            "Transfers",
            "Demotions",
            "Retirements",
            "Disciplinary",
          ],
          data: [2, 1, 0, 0, 0, 1],
        },
        activity_trends: {
          labels: [
            "Jan 2024",
            "Feb 2024",
            "Mar 2024",
            "Apr 2024",
            "May 2024",
            "Jun 2024",
          ],
          datasets: [
            { label: "Promotions", data: [0, 1, 0, 0, 1, 0] },
            { label: "Transfers", data: [1, 0, 0, 0, 0, 0] },
            { label: "Retirements", data: [0, 0, 0, 0, 0, 0] },
            { label: "Demotions", data: [0, 0, 0, 0, 0, 0] },
          ],
        },
        promotions_by_grade: { labels: ["Level 2", "Level 3"], data: [1, 1] },
        transfers_by_branch: { labels: ["Bole Branch"], data: [1] },
        retirements_by_type: { labels: ["Normal"], data: [0] },
        disciplinary_by_type: { labels: ["Warning"], data: [0] },
      };

      this.state.availableFilters = {
        branches: [
          { id: 1, name: "Head Office" },
          { id: 2, name: "Bole Branch" },
          { id: 3, name: "Piazza Branch" },
        ],
        departments: [
          { id: 1, name: "Human Resources" },
          { id: 2, name: "Information Technology" },
          { id: 3, name: "Finance" },
        ],
        genders: [
          { id: "m", name: "M" },
          { id: "f", name: "F" },
        ],
        age_groups: [
          { id: "20_29", name: "20-29" },
          { id: "30_39", name: "30-39" },
          { id: "40_49", name: "40-49" },
          { id: "50_59", name: "50-59" },
        ],
        job_positions: [
          { id: 1, name: "Manager" },
          { id: 2, name: "Developer" },
          { id: 3, name: "Analyst" },
        ],
        grades: [
          { id: 1, name: "Level 1" },
          { id: 2, name: "Level 2" },
          { id: 3, name: "Level 3" },
        ],
        districts: [
          { id: 1, name: "Addis Ababa" },
          { id: 2, name: "Oromia" },
          { id: 3, name: "Amhara" },
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

      console.log("Filter changed:", { [filterName]: filterValue });

      await this.fetchDashboardData();

      setTimeout(() => {
        this.renderAllCharts();
      }, 100);
    }
  }

  renderAllCharts() {
    if (this.state.loading) return;

    console.log("Rendering all charts for tab:", this.state.activeTab);
    this.destroyCharts();

    try {
      switch (this.state.activeTab) {
        case "overview":
          this.renderOverviewCharts();
          break;
        case "movements":
          this.renderMovementCharts();
          break;
        case "structure":
          this.renderStructureCharts();
          break;
        case "activities":
          this.renderActivityCharts();
          break;
      }
    } catch (error) {
      console.error("Error rendering charts:", error);
    }
  }

  setActiveTab(tabName) {
    console.log("Setting active tab to:", tabName);
    this.state.activeTab = tabName;
    // Delay to allow DOM to update
    setTimeout(() => this.renderAllCharts(), 100);
  }

  renderOverviewCharts() {
    console.log("Rendering overview charts");

    this._renderDoughnutChart(
      "gender",
      this.chartRefs.gender.el,
      this.state.charts.by_gender,
      "Gender Breakdown"
    );

    this._renderBarChart(
      "age",
      this.chartRefs.age.el,
      this.state.charts.by_age,
      "Age Distribution",
      true
    );

    this._renderPieChart(
      "location",
      this.chartRefs.location.el,
      this.state.charts.by_location,
      "Work Location"
    );

    this._renderPieChart(
      "positionClassification",
      this.chartRefs.positionClassification.el,
      this.state.charts.by_position_classification,
      "Position Classification"
    );
  }

  renderMovementCharts() {
    console.log("Rendering movement charts");

    this._renderLineChart(
      "hires",
      this.chartRefs.hires.el,
      this.state.charts.hires_over_time,
      "New Hires Trend"
    );

    this._renderMultiLineChart(
      "activityTrends",
      this.chartRefs.activityTrends.el,
      this.state.charts.activity_trends,
      "Activity Trends Over Time"
    );
  }

  renderStructureCharts() {
    console.log("Rendering structure charts");

    this._renderBarChart(
      "department",
      this.chartRefs.department.el,
      this.state.charts.by_department,
      "Employees by Department",
      true
    );

    this._renderBarChart(
      "grade",
      this.chartRefs.grade.el,
      this.state.charts.by_grade,
      "Employees by Grade"
    );

    this._renderBarChart(
      "jobPosition",
      this.chartRefs.jobPosition.el,
      this.state.charts.by_job_position,
      "Employees by Job Position",
      true
    );

    this._renderBarChart(
      "district",
      this.chartRefs.district.el,
      this.state.charts.by_district,
      "Employees by District"
    );
  }

  renderActivityCharts() {
    console.log("Rendering activity charts");

    this._renderDoughnutChart(
      "activitySummary",
      this.chartRefs.activitySummary.el,
      this.state.charts.activity_summary,
      "Activity Summary"
    );

    this._renderBarChart(
      "promotionsByGrade",
      this.chartRefs.promotionsByGrade.el,
      this.state.charts.promotions_by_grade,
      "Promotions by Grade"
    );

    this._renderBarChart(
      "transfersByBranch",
      this.chartRefs.transfersByBranch.el,
      this.state.charts.transfers_by_branch,
      "Transfers by Branch",
      true
    );

    this._renderPieChart(
      "retirementsByType",
      this.chartRefs.retirementsByType.el,
      this.state.charts.retirements_by_type,
      "Retirements by Type"
    );

    this._renderPieChart(
      "disciplinaryByType",
      this.chartRefs.disciplinaryByType.el,
      this.state.charts.disciplinary_by_type,
      "Disciplinary Actions by Type"
    );
  }

  _renderChart(type, chartId, canvas, chartData, title, options = {}) {
    if (!canvas) {
      console.warn(`Canvas not found for chart: ${chartId}`);
      return;
    }

    if (!chartData || !chartData.labels || !chartData.data) {
      console.warn(`Invalid chart data for: ${chartId}`, chartData);
      return;
    }

    if (chartData.labels.length === 0) {
      canvas.parentElement.innerHTML +=
        '<p class="text-muted text-center mt-5">No data available for this chart.</p>';
      console.warn(`Empty chart data for: ${chartId}`);
      return;
    }

    try {
      const ctx = canvas.getContext("2d");

      const baseOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: "bottom",
            labels: {
              font: { size: 12 },
              usePointStyle: true,
              padding: 20,
            },
          },
          tooltip: {
            backgroundColor: "rgba(0, 0, 0, 0.8)",
            titleColor: "#fff",
            bodyColor: "#fff",
            borderColor: "#860037",
            borderWidth: 1,
          },
        },
      };

      this.charts[chartId] = new Chart(ctx, {
        type,
        data: {
          labels: chartData.labels,
          datasets: [
            {
              label: title,
              data: chartData.data,
              backgroundColor: this.chartColors.slice(0, chartData.data.length),
              borderColor: type.includes("line")
                ? this.chartColors.slice(0, chartData.data.length)
                : "#fff",
              borderWidth: type.includes("bar") ? 0 : 2,
              tension: 0.4,
              fill: type.includes("line") ? false : true,
            },
          ],
        },
        options: { ...baseOptions, ...options },
      });

      console.log(`Successfully rendered chart: ${chartId}`);
    } catch (error) {
      console.error(`Error rendering chart ${chartId}:`, error);
    }
  }

  _renderMultiLineChart(id, el, data, title) {
    if (!el || !data || !data.labels || !data.datasets) {
      console.warn(`Invalid multi-line chart data for: ${id}`, data);
      return;
    }

    try {
      const datasets = data.datasets.map((dataset, index) => ({
        ...dataset,
        borderColor: this.chartColors[index % this.chartColors.length],
        backgroundColor:
          this.chartColors[index % this.chartColors.length] + "20",
        tension: 0.4,
        fill: false,
        pointBackgroundColor: this.chartColors[index % this.chartColors.length],
        pointBorderColor: "#fff",
        pointBorderWidth: 2,
        pointRadius: 4,
      }));

      const ctx = el.getContext("2d");

      this.charts[id] = new Chart(ctx, {
        type: "line",
        data: {
          labels: data.labels,
          datasets: datasets,
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: "top",
              labels: {
                usePointStyle: true,
                padding: 20,
              },
            },
            tooltip: {
              mode: "index",
              intersect: false,
              backgroundColor: "rgba(0, 0, 0, 0.8)",
              titleColor: "#fff",
              bodyColor: "#fff",
            },
          },
          scales: {
            x: {
              grid: {
                color: "rgba(0, 0, 0, 0.1)",
              },
            },
            y: {
              beginAtZero: true,
              grid: {
                color: "rgba(0, 0, 0, 0.1)",
              },
            },
          },
          interaction: {
            mode: "nearest",
            axis: "x",
            intersect: false,
          },
        },
      });

      console.log(`Successfully rendered multi-line chart: ${id}`);
    } catch (error) {
      console.error(`Error rendering multi-line chart ${id}:`, error);
    }
  }

  _renderPieChart(id, el, data, title) {
    this._renderChart("pie", id, el, data, title, {
      plugins: {
        legend: {
          position: "right",
          labels: {
            generateLabels: function (chart) {
              const data = chart.data;
              if (data.labels.length && data.datasets.length) {
                return data.labels.map((label, i) => {
                  const value = data.datasets[0].data[i];
                  const total = data.datasets[0].data.reduce(
                    (a, b) => a + b,
                    0
                  );
                  const percentage =
                    total > 0 ? ((value / total) * 100).toFixed(1) : 0;
                  return {
                    text: `${label}: ${percentage}%`,
                    fillStyle: data.datasets[0].backgroundColor[i],
                    strokeStyle: data.datasets[0].backgroundColor[i],
                    lineWidth: 0,
                    pointStyle: "circle",
                    hidden: false,
                    index: i,
                  };
                });
              }
              return [];
            },
          },
        },
      },
    });
  }

  _renderDoughnutChart(id, el, data, title) {
    this._renderChart("doughnut", id, el, data, title, {
      cutout: "60%",
      plugins: {
        legend: {
          position: "bottom",
          labels: {
            generateLabels: function (chart) {
              const data = chart.data;
              if (data.labels.length && data.datasets.length) {
                return data.labels.map((label, i) => {
                  const value = data.datasets[0].data[i];
                  const total = data.datasets[0].data.reduce(
                    (a, b) => a + b,
                    0
                  );
                  const percentage =
                    total > 0 ? ((value / total) * 100).toFixed(1) : 0;
                  return {
                    text: `${label}: ${value} (${percentage}%)`,
                    fillStyle: data.datasets[0].backgroundColor[i],
                    strokeStyle: data.datasets[0].backgroundColor[i],
                    lineWidth: 0,
                    pointStyle: "circle",
                    hidden: false,
                    index: i,
                  };
                });
              }
              return [];
            },
          },
        },
      },
    });
  }

  _renderLineChart(id, el, data, title) {
    this._renderChart("line", id, el, data, title, {
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            title: function (context) {
              return context[0].label;
            },
            label: function (context) {
              return `${title}: ${context.parsed.y}`;
            },
          },
        },
      },
      scales: {
        x: {
          grid: {
            color: "rgba(0, 0, 0, 0.1)",
          },
        },
        y: {
          beginAtZero: true,
          grid: {
            color: "rgba(0, 0, 0, 0.1)",
          },
        },
      },
    });
  }

  _renderBarChart(id, el, data, title, isHorizontal = false) {
    this._renderChart("bar", id, el, data, title, {
      indexAxis: isHorizontal ? "y" : "x",
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            title: function (context) {
              return context[0].label;
            },
            label: function (context) {
              return `${title}: ${context.parsed[isHorizontal ? "x" : "y"]}`;
            },
          },
        },
      },
      scales: {
        x: {
          beginAtZero: true,
          grid: {
            color: "rgba(0, 0, 0, 0.1)",
          },
        },
        y: {
          beginAtZero: true,
          grid: {
            color: "rgba(0, 0, 0, 0.1)",
          },
        },
      },
    });
  }

  destroyCharts() {
    Object.values(this.charts).forEach((chart) => {
      if (chart && typeof chart.destroy === "function") {
        try {
          chart.destroy();
        } catch (error) {
          console.warn("Error destroying chart:", error);
        }
      }
    });
    this.charts = {};
  }
}

AhaduHRReportingDashboard.template = "ahadu_hr.HRReportingDashboard";

registry
  .category("actions")
  .add("ahadu_hr.reporting_dashboard", AhaduHRReportingDashboard);
