/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class UserManualViewer extends Component {
    setup() {
        this.actionService = useService("action");
        this.pdfUrl = "/ahadu_attendance/static/docs/Ahadu_Attendance_User_Manual.pdf";
    }

    onDownload() {
        const link = document.createElement("a");
        link.href = this.pdfUrl;
        link.download = "Ahadu_Attendance_User_Manual.pdf";
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }
}

UserManualViewer.template = "ahadu_attendance.UserManualViewer";

registry.category("actions").add("ahadu_attendance.user_manual", UserManualViewer);
