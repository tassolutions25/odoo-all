import { Component, useState, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class EmployeeActivityDashboard extends Component {
  setup() {
    this.orm = useService("orm");
    this.action = useService("action");
  }

  async onActivityClick(activityType) {
    let action;
    switch (activityType) {
      // case "employees":
      //   action = {
      //     type: "ir.actions.act_window",
      //     res_model: "hr.employee",
      //     view_mode: "list,form,graph",
      //     views: [
      //       [false, "list"],
      //       [false, "form"],
      //       [false, "graph"],
      //     ],
      //     name: "Employees",
      //   };
      //   break;
      case "demotion":
        action = {
          type: "ir.actions.act_window",
          res_model: "hr.employee.demotion",
          view_mode: "list,form,graph",
          views: [
            [false, "list"],
            [false, "form"],
            [false, "graph"],
          ],
          name: "Employee Demotions",
        };
        break;
      case "promotion":
        action = {
          type: "ir.actions.act_window",
          res_model: "hr.employee.promotion",
          view_mode: "list,form,graph",
          views: [
            [false, "list"],
            [false, "form"],
            [false, "graph"],
          ],
          name: "Employee Promotions",
        };
        break;
      case "transfer":
        action = {
          type: "ir.actions.act_window",
          res_model: "hr.employee.transfer",
          view_mode: "list,form,graph",
          views: [
            [false, "list"],
            [false, "form"],
            [false, "graph"],
          ],
          name: "Employee Transfers",
        };
        break;
      case "termination":
        action = {
          type: "ir.actions.act_window",
          res_model: "hr.employee.termination",
          view_mode: "list,form,graph",
          views: [
            [false, "list"],
            [false, "form"],
            [false, "graph"],
          ],
          name: "Employee Terminations",
        };
        break;
      case "resignation":
        action = {
          type: "ir.actions.act_window",
          res_model: "hr.employee.resignation",
          view_mode: "list,form,graph",
          views: [
            [false, "list"],
            [false, "form"],
            [false, "graph"],
          ],
          name: "Employee resignations",
        };
        break;
      case "acting":
        action = {
          type: "ir.actions.act_window",
          res_model: "hr.employee.acting",
          view_mode: "list,form,graph",
          views: [
            [false, "list"],
            [false, "form"],
            [false, "graph"],
          ],
          name: "Acting Assignments",
        };
        break;
      case "temporary":
        action = {
          type: "ir.actions.act_window",
          res_model: "hr.employee.temporary.assignment",
          view_mode: "list,form,graph",
          views: [
            [false, "list"],
            [false, "form"],
            [false, "graph"],
          ],
          name: "Temporary Assignments",
        };
        break;
      case "suspension":
        action = {
          type: "ir.actions.act_window",
          res_model: "hr.employee.suspension",
          view_mode: "list,form",
          views: [
            [false, "list"],
            [false, "form"],
            [false, "graph"],
          ],
          name: "Suspensions",
        };
        break;
      case "disciplinary":
        action = {
          type: "ir.actions.act_window",
          res_model: "hr.employee.disciplinary",
          view_mode: "list,form,graph",
          views: [
            [false, "list"],
            [false, "form"],
            [false, "graph"],
          ],
          name: "Disciplinary Actions",
        };
        break;
      case "ctc":
        action = {
          type: "ir.actions.act_window",
          res_model: "hr.employee.ctc",
          view_mode: "list,form",
          views: [
            [false, "list"],
            [false, "form"],
          ],
          name: "CTC Adjustments",
        };
        break;
      case "guarantee":
        action = {
          type: "ir.actions.act_window",
          res_model: "hr.employee.guarantee",
          view_mode: "list,form,graph",
          views: [
            [false, "list"],
            [false, "form"],
            [false, "graph"],
          ],
          name: "Employee Guarantees",
        };
        break;
      case "retirement":
        action = {
          type: "ir.actions.act_window",
          res_model: "hr.employee.retirement",
          view_mode: "list,form",
          views: [
            [false, "list"],
            [false, "form"],
          ],
          name: "Employee Retirements",
        };
        break;
      case "data_change":
        action = {
          type: "ir.actions.act_window",
          res_model: "hr.employee.data.change",
          view_mode: "list,form",
          views: [
            [false, "list"],
            [false, "form"],
          ],
          name: "Employee Data Changes",
        };
        break;
      case "confirmation":
        action = {
          type: "ir.actions.act_window",
          res_model: "hr.employee.confirmation",
          view_mode: "list,form",
          views: [
            [false, "list"],
            [false, "form"],
          ],
          name: "Employee Confirmations",
        };
        break;
      case "reassign_reportees":
        action = {
          type: "ir.actions.act_window",
          res_model: "hr.employee.reassign",
          view_mode: "list,form",
          views: [
            [false, "list"],
            [false, "form"],
          ],
          name: "Reassign Reportees",
        };
        break;
      case "employee_reinitiate":
        action = {
          type: "ir.actions.act_window",
          res_model: "hr.employee.reinitiate",
          view_mode: "list,form",
          views: [
            [false, "list"],
            [false, "form"],
          ],
          name: "Employee Re-initiate",
        };
        break;
      case "onboarding":
        action = "ahadu_hr_self_service.action_hr_employee_onboarding";
        break;
      case "document_request":
        action = "ahadu_hr_self_service.action_hr_document_request";
        break;
      default:
        return;
    }

    if (action) {
      await this.action.doAction(action);
    }
  }
}

EmployeeActivityDashboard.template = xml`
<div class="o_employee_activities_dashboard p-4 h-100 overflow-auto">
    <h1 class="text-center mb-4">Employee Activities</h1>
    <div class="row">
        <div class="col-lg-3 col-md-4 mb-4">
            <div class="card activity-card h-100" t-on-click="() => this.onActivityClick('onboarding')">
                <div class="card-body text-center d-flex flex-column justify-content-center">
                    <i class="fa fa-user-check fa-3x" style="color: #860037;"></i>
                    <h5 class="mt-3">Onboarding</h5>
                </div>
            </div>
        </div>
        <div class="col-lg-3 col-md-4 mb-4">
            <div class="card activity-card h-100" t-on-click="() => this.onActivityClick('document_request')">
                <div class="card-body text-center d-flex flex-column justify-content-center">
                    <i class="fa fa-file-signature fa-3x" style="color: #860037;"></i>
                    <h5 class="mt-3">Document Request</h5>
                </div>
            </div>
        </div>
        <div class="col-lg-3 col-md-4 mb-4">
            <div class="card activity-card h-100" t-on-click="() => this.onActivityClick('promotion')">
                <div class="card-body text-center d-flex flex-column justify-content-center">
                    <i class="fa fa-arrow-up fa-3x" style="color: #860037;"></i>
                    <h5 class="mt-3">Promotion</h5>
                </div>
            </div>
        </div>
        <div class="col-lg-3 col-md-4 mb-4">
            <div class="card activity-card h-100" t-on-click="() => this.onActivityClick('demotion')">
                <div class="card-body text-center d-flex flex-column justify-content-center">
                    <i class="fa fa-arrow-down fa-3x" style="color: #860037;"></i>
                    <h5 class="mt-3">Demotion</h5>
                </div>
            </div>
        </div>
        <div class="col-lg-3 col-md-4 mb-4">
            <div class="card activity-card h-100" t-on-click="() => this.onActivityClick('transfer')">
                <div class="card-body text-center d-flex flex-column justify-content-center">
                    <i class="fa fa-random fa-3x" style="color: #860037;"></i>
                    <h5 class="mt-3">Transfer</h5>
                </div>
            </div>
        </div>
        
        <div class="col-lg-3 col-md-4 mb-4">
            <div class="card activity-card h-100" t-on-click="() => this.onActivityClick('acting')">
                <div class="card-body text-center d-flex flex-column justify-content-center">
                    <i class="fa fa-user-tie fa-3x" style="color: #860037;"></i>
                    <h5 class="mt-3">Acting Assignment</h5>
                </div>
            </div>
        </div>
        <div class="col-lg-3 col-md-4 mb-4">
            <div class="card activity-card h-100" t-on-click="() => this.onActivityClick('temporary')">
                <div class="card-body text-center d-flex flex-column justify-content-center">
                    <i class="fa fa-user-clock fa-3x" style="color: #860037;"></i>
                    <h5 class="mt-3">Temporary Assignment</h5>
                </div>
            </div>
        </div>
        <div class="col-lg-3 col-md-4 mb-4">
            <div class="card activity-card h-100" t-on-click="() => this.onActivityClick('termination')">
                <div class="card-body text-center d-flex flex-column justify-content-center">
                    <i class="fa fa-user-minus fa-3x" style="color: #860037;"></i>
                    <h5 class="mt-3">Termination</h5>
                </div>
            </div>
        </div>
        <div class="col-lg-3 col-md-4 mb-4">
          <div class="card activity-card h-100" t-on-click="() => this.onActivityClick('resignation')">
              <div class="card-body text-center d-flex flex-column justify-content-center">
                  <i class="fa fa-user-times fa-3x" style="color: #860037;"></i>
                  <h5 class="mt-3">Resignation</h5>
              </div>
          </div>
      </div>
      <div class="col-lg-3 col-md-4 mb-4">
        <div class="card activity-card h-100" t-on-click="() => this.onActivityClick('suspension')">
            <div class="card-body text-center d-flex flex-column justify-content-center">
                <i class="fa fa-user-times fa-3x" style="color: #860037;"></i>
                <h5 class="mt-3">Suspension</h5>
            </div>
        </div>
      </div>
        <div class="col-lg-3 col-md-4 mb-4">
            <div class="card activity-card h-100" t-on-click="() => this.onActivityClick('disciplinary')">
                <div class="card-body text-center d-flex flex-column justify-content-center">
                    <i class="fa fa-gavel fa-3x" style="color: #860037;"></i>
                    <h5 class="mt-3">Disciplinary Actions</h5>
                </div>
            </div>
        </div>
        <div class="col-lg-3 col-md-4 mb-4">
            <div class="card activity-card h-100" t-on-click="() => this.onActivityClick('guarantee')">
                <div class="card-body text-center d-flex flex-column justify-content-center">
                    <i class="fa fa-shield fa-3x" style="color: #860037;"></i>
                    <h5 class="mt-3">Employee Guarantees</h5>
                </div>
            </div>
        </div>
        <div class="col-lg-3 col-md-4 mb-4">
            <div class="card activity-card h-100" t-on-click="() => this.onActivityClick('retirement')">
                <div class="card-body text-center d-flex flex-column justify-content-center">
                    <i class="fa fa-random fa-3x" style="color: #860037;"></i>
                    <h5 class="mt-3">retirement</h5>
                </div>
            </div>
        </div>
        <div class="col-lg-3 col-md-4 mb-4">
            <div class="card activity-card h-100" t-on-click="() => this.onActivityClick('ctc')">
                <div class="card-body text-center d-flex flex-column justify-content-center">
                    <i class="fa fa-money fa-3x" style="color: #860037;"></i>
                    <h5 class="mt-3">CTC Adjustments</h5>
                </div>
            </div>
        </div>
        <div class="col-lg-3 col-md-4 mb-4">
            <div class="card activity-card h-100" t-on-click="() => this.onActivityClick('data_change')">
                <div class="card-body text-center d-flex flex-column justify-content-center">
                    <i class="fa fa-random fa-3x" style="color: #860037;"></i>
                    <h5 class="mt-3">Data Change</h5>
                </div>
            </div>
        </div>
        <div class="col-lg-3 col-md-4 mb-4">
            <div class="card activity-card h-100" t-on-click="() => this.onActivityClick('confirmation')">
                <div class="card-body text-center d-flex flex-column justify-content-center">
                    <i class="fa fa-random fa-3x" style="color: #860037;"></i>
                    <h5 class="mt-3">Confirmation</h5>
                </div>
            </div>
        </div>
        <div class="col-lg-3 col-md-4 mb-4">
            <div class="card activity-card h-100" t-on-click="() => this.onActivityClick('reassign_reportees')">
                <div class="card-body text-center d-flex flex-column justify-content-center">
                    <i class="fa fa-random fa-3x" style="color: #860037;"></i>
                    <h5 class="mt-3">Reassign Reportees</h5>
                </div>
            </div>
        </div>
        <div class="col-lg-3 col-md-4 mb-4">
            <div class="card activity-card h-100" t-on-click="() => this.onActivityClick('employee_reinitiate')">
                <div class="card-body text-center d-flex flex-column justify-content-center">
                    <i class="fa fa-random fa-3x" style="color: #860037;"></i>
                    <h5 class="mt-3">Employee Re-initiate</h5>
                </div>
            </div>
        </div>
    </div>
</div>
`;

registry
  .category("actions")
  .add("employee_activity_dashboard", EmployeeActivityDashboard);
