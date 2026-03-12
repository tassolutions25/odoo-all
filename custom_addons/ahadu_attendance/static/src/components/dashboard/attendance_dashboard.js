/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Layout } from "@web/search/layout";
import { KpiCard } from "@ahadu_attendance/components/chart_renderer/kpi_card";
import { ChartRenderer } from "@ahadu_attendance/components/chart_renderer/chart_renderer";

class AhaduAttendanceDashboard extends Component {
    static template = "ahadu_attendance.AttendanceDashboard";
    static components = { Layout, KpiCard, ChartRenderer };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        const today = new Date();
        this.state = useState({
            kpi_data: {},
            chart_data: {},
            realtime_logs: [],
            summary_data: {},
            uid: null,
            filters: {
                month: today.getMonth() + 1,   
                year: today.getFullYear(),
                employee_id: null,
            },
            employees: [],
            searchQuery: "",
        });

        onWillStart(async () => {
            await this.fetchEmployees();
            await this.fetchDashboardData();
        });
    }

    async fetchEmployees() {
        this.state.employees = await this.orm.searchRead("hr.employee", [["active", "=", true]], ["id", "name", "employee_id"]);
    }

    async fetchDashboardData() {
        try {
            const data = await this.orm.call("hr.attendance", "get_attendance_dashboard_data", [], {
                filters: {
                    month: this.state.filters.month,
                    year: this.state.filters.year,
                    employee_id: this.state.filters.employee_id,
                }
            });
            if (data) {
                Object.assign(this.state, data);
                if (data.summary_data && data.summary_data.current_employee) {
                    this.state.searchQuery = data.summary_data.current_employee.name;
                }
            }
        } catch (error) {
            console.error("Dashboard data fetch failed:", error);
        }
    }

    async onFilterChange() {
        await this.fetchDashboardData();
    }

    async onEmployeeSearch(ev) {
        this.state.searchQuery = ev.target.value;
    }

    async selectEmployee(employee) {
        this.state.filters.employee_id = employee.id;
        this.state.searchQuery = employee.name;
        await this.fetchDashboardData();
    }

    get filteredEmployees() {
        if (!this.state.searchQuery) return [];
        const query = this.state.searchQuery.toLowerCase();
        return this.state.employees.filter(e =>
            e.name.toLowerCase().includes(query) ||
            (e.employee_id && e.employee_id.toLowerCase().includes(query))
        ).slice(0, 10);
    }

    get years() {
        const currentYear = new Date().getFullYear();
        const years = [];
        for (let i = currentYear - 5; i <= currentYear + 1; i++) {
            years.push(i);
        }
        return years;
    }

    get months() {
        return [
            { id: 1, name: "January" }, { id: 2, name: "February" }, { id: 3, name: "March" },
            { id: 4, name: "April" }, { id: 5, name: "May" }, { id: 6, name: "June" },
            { id: 7, name: "July" }, { id: 8, name: "August" }, { id: 9, name: "September" },
            { id: 10, name: "October" }, { id: 11, name: "November" }, { id: 12, name: "December" }
        ];
    }

    // --- Action Methods ---

    /**
     * FIX: Added missing openRecords method called by XML template
     * @param {String} name - Title of the window
     * @param {String} resModel - The model to open (e.g., 'hr.leave')
     * @param {Array} domain - The search domain
     */
    openRecords(name, resModel, domain) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: name,
            res_model: resModel,
            views: [[false, "list"], [false, "form"]],
            view_mode: "list,form",
            domain: domain,
            target: "current",
        });
    }

    openAttendances(domain) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Attendances",
            res_model: "hr.attendance",
            views: [[false, "list"], [false, "form"]],
            domain: domain || [["employee_id.user_id", "=", this.state.uid]],
        });
    }

    openMonthAttendances() {
        const today = new Date();
        const startOfMonth = new Date(today.getFullYear(), today.getMonth(), 1).toISOString().split('T')[0] + " 00:00:00";
        const endOfMonth = new Date(today.getFullYear(), today.getMonth() + 1, 0).toISOString().split('T')[0] + " 23:59:59";

        this.openAttendances([
            ["employee_id.user_id", "=", this.state.uid],
            ["check_in", ">=", startOfMonth],
            ["check_in", "<=", endOfMonth]
        ]);
    }

    openFilteredAttendances(status) {
        const today = new Date();
        const startOfMonth = new Date(today.getFullYear(), today.getMonth(), 1).toISOString().split('T')[0] + " 00:00:00";
        const endOfMonth = new Date(today.getFullYear(), today.getMonth() + 1, 0).toISOString().split('T')[0] + " 23:59:59";

        let domain = [
            ["employee_id.user_id", "=", this.state.uid],
            ["check_in", ">=", startOfMonth],
            ["check_in", "<=", endOfMonth]
        ];

        if (status === 'on_time') {
            domain.push(["attendance_status", "in", ["on_time"]]);
        } else if (status === 'issue') {
            domain.push(["attendance_status", "in", ["late_in", "early_out", "late_in_miss_out"]]);
        } else if (status === 'absent') {
            // "Absent" record in attendance is usually a Miss Out
            domain.push(["attendance_status", "in", ["miss_out"]]);
        } else if (status === 'leave') {
            this.action.doAction({
                type: "ir.actions.act_window",
                name: "My Leaves",
                res_model: "hr.leave",
                views: [[false, "list"], [false, "form"]],
                domain: [
                    ["employee_id.user_id", "=", this.state.uid],
                    ["request_date_from", "<=", endOfMonth.split(' ')[0]],
                    ["request_date_to", ">=", startOfMonth.split(' ')[0]]
                ],
            });
            return;
        }

        this.action.doAction({
            type: "ir.actions.act_window",
            name: `My ${status.charAt(0).toUpperCase() + status.slice(1)} records`,
            res_model: "hr.attendance",
            views: [[false, "list"], [false, "form"]],
            domain: domain,
        });
    }

    openAbsences() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Absent Employees",
            res_model: "hr.employee",
            views: [[false, "kanban"], [false, "list"], [false, "form"]],
            domain: this.state.kpi_data.domain_absent,
            context: { 'search_default_absent_today': 1 }
        });
    }

    onDayClick(day) {
        if (!day.full_date) return;
        this.openAttendances([
            ["employee_id.user_id", "=", this.state.uid],
            ["check_in", ">=", day.full_date + " 00:00:00"],
            ["check_in", "<=", day.full_date + " 23:59:59"]
        ]);
    }
}

registry.category("actions").add("ahadu_attendance.dashboard", AhaduAttendanceDashboard);





// /** @odoo-module **/

// import { registry } from "@web/core/registry";
// import { Component, onWillStart, useState } from "@odoo/owl";
// import { useService } from "@web/core/utils/hooks";
// import { Layout } from "@web/search/layout";
// import { KpiCard } from "@ahadu_attendance/components/chart_renderer/kpi_card";
// import { ChartRenderer } from "@ahadu_attendance/components/chart_renderer/chart_renderer";

// class AhaduAttendanceDashboard extends Component {
//     static template = "ahadu_attendance.AttendanceDashboard";
//     static components = { Layout, KpiCard, ChartRenderer };

//     setup() {
//         this.orm = useService("orm");
//         this.action = useService("action");
//         const today = new Date();
//         this.state = useState({
//             kpi_data: {},
//             chart_data: {},
//             realtime_logs: [],
//             summary_data: {},
//             uid: null,
//             filters: {
//                 month: today.getMonth() + 1,
//                 year: today.getFullYear(),
//                 employee_id: null,
//             },
//             employees: [],
//             searchQuery: "",
//         });

//         onWillStart(async () => {
//             await this.fetchEmployees();
//             await this.fetchDashboardData();
//         });
//     }

//     async fetchEmployees() {
//         this.state.employees = await this.orm.searchRead("hr.employee", [["active", "=", true]], ["id", "name", "employee_id"]);
//     }

//     async fetchDashboardData() {
//         try {
//             const data = await this.orm.call("hr.attendance", "get_attendance_dashboard_data", [], {
//                 filters: {
//                     month: this.state.filters.month,
//                     year: this.state.filters.year,
//                     employee_id: this.state.filters.employee_id,
//                 }
//             });
//             if (data) {
//                 Object.assign(this.state, data);
//                 if (data.summary_data && data.summary_data.current_employee) {
//                     this.state.searchQuery = data.summary_data.current_employee.name;
//                 }
//             }
//         } catch (error) {
//             console.error("Dashboard data fetch failed:", error);
//         }
//     }

//     async onFilterChange() {
//         await this.fetchDashboardData();
//     }

//     async onEmployeeSearch(ev) {
//         this.state.searchQuery = ev.target.value;
//     }

//     async selectEmployee(employee) {
//         this.state.filters.employee_id = employee.id;
//         this.state.searchQuery = employee.name;
//         await this.fetchDashboardData();
//     }

//     get filteredEmployees() {
//         if (!this.state.searchQuery) return [];
//         const query = this.state.searchQuery.toLowerCase();
//         return this.state.employees.filter(e =>
//             e.name.toLowerCase().includes(query) ||
//             (e.employee_id && e.employee_id.toLowerCase().includes(query))
//         ).slice(0, 10);
//     }

//     get years() {
//         const currentYear = new Date().getFullYear();
//         const years = [];
//         for (let i = currentYear - 5; i <= currentYear + 1; i++) {
//             years.push(i);
//         }
//         return years;
//     }

//     get months() {
//         return [
//             { id: 1, name: "January" }, { id: 2, name: "February" }, { id: 3, name: "March" },
//             { id: 4, name: "April" }, { id: 5, name: "May" }, { id: 6, name: "June" },
//             { id: 7, name: "July" }, { id: 8, name: "August" }, { id: 9, name: "September" },
//             { id: 10, name: "October" }, { id: 11, name: "November" }, { id: 12, name: "December" }
//         ];
//     }

//     // --- Action Methods ---
//     openAttendances(domain) {
//         this.action.doAction({
//             type: "ir.actions.act_window",
//             name: "Attendances",
//             res_model: "hr.attendance",
//             views: [[false, "list"], [false, "form"]],
//             domain: domain || [["employee_id.user_id", "=", this.state.uid]],
//         });
//     }

//     openMonthAttendances() {
//         const today = new Date();
//         const startOfMonth = new Date(today.getFullYear(), today.getMonth(), 1).toISOString().split('T')[0] + " 00:00:00";
//         const endOfMonth = new Date(today.getFullYear(), today.getMonth() + 1, 0).toISOString().split('T')[0] + " 23:59:59";

//         this.openAttendances([
//             ["employee_id.user_id", "=", this.state.uid],
//             ["check_in", ">=", startOfMonth],
//             ["check_in", "<=", endOfMonth]
//         ]);
//     }

//     openFilteredAttendances(status) {
//         const today = new Date();
//         const startOfMonth = new Date(today.getFullYear(), today.getMonth(), 1).toISOString().split('T')[0] + " 00:00:00";
//         const endOfMonth = new Date(today.getFullYear(), today.getMonth() + 1, 0).toISOString().split('T')[0] + " 23:59:59";

//         let domain = [
//             ["employee_id.user_id", "=", this.state.uid],
//             ["check_in", ">=", startOfMonth],
//             ["check_in", "<=", endOfMonth]
//         ];

//         if (status === 'on_time') {
//             domain.push(["attendance_status", "in", ["on_time"]]);
//         } else if (status === 'issue') {
//             domain.push(["attendance_status", "in", ["late_in", "early_out", "late_in_miss_out"]]);
//         } else if (status === 'absent') {
//             // "Absent" record in attendance is usually a Miss Out
//             domain.push(["attendance_status", "in", ["miss_out"]]);
//         } else if (status === 'leave') {
//             this.action.doAction({
//                 type: "ir.actions.act_window",
//                 name: "My Leaves",
//                 res_model: "hr.leave",
//                 views: [[false, "list"], [false, "form"]],
//                 domain: [
//                     ["employee_id.user_id", "=", this.state.uid],
//                     ["request_date_from", "<=", endOfMonth.split(' ')[0]],
//                     ["request_date_to", ">=", startOfMonth.split(' ')[0]]
//                 ],
//             });
//             return;
//         }

//         this.action.doAction({
//             type: "ir.actions.act_window",
//             name: `My ${status.charAt(0).toUpperCase() + status.slice(1)} records`,
//             res_model: "hr.attendance",
//             views: [[false, "list"], [false, "form"]],
//             domain: domain,
//         });
//     }

//     openAbsences() {
//         this.action.doAction({
//             type: "ir.actions.act_window",
//             name: "Absent Employees",
//             res_model: "hr.employee",
//             views: [[false, "kanban"], [false, "list"], [false, "form"]],
//             domain: this.state.kpi_data.domain_absent,
//             context: { 'search_default_absent_today': 1 }
//         });
//     }

//     onDayClick(day) {
//         if (!day.full_date) return;
//         this.openAttendances([
//             ["employee_id.user_id", "=", this.state.uid],
//             ["check_in", ">=", day.full_date + " 00:00:00"],
//             ["check_in", "<=", day.full_date + " 23:59:59"]
//         ]);
//     }
// }

// registry.category("actions").add("ahadu_attendance.dashboard", AhaduAttendanceDashboard);