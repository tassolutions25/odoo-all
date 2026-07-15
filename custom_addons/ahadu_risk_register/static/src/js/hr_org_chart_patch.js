/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { HrOrgChart } from "@hr_org_chart/fields/hr_org_chart";

const originalFetchEmployeeData = HrOrgChart.prototype.fetchEmployeeData;

patch(HrOrgChart.prototype, {
    async fetchEmployeeData(employeeId, force = false) {
        let correctedEmployeeId = employeeId;
        const record = this.props.record;
        
        // If the active model is employee, we want the employee's own primary key (resId),
        // not the string value of the character field 'employee_id' (Badge ID).
        if (record && record.resModel && (record.resModel === 'hr.employee' || record.resModel === 'hr.employee.public')) {
            correctedEmployeeId = record.resId || false;
        }
        
        return originalFetchEmployeeData.call(this, correctedEmployeeId, force);
    }
});
