import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";

export class AhaduCalendarView extends Component {
    static template = "ahadu_hr_leave.AhaduCalendarView";


    setup() {
        this.orm = useService("orm");
        this.state = useState({
            year: new Date().getFullYear(),
            calendarData: { months: [], legend_data: {} },

           
        });

        onWillStart(async () => {
            await this.fetchCalendarData();
        });
    }

    async fetchCalendarData() {
        const data = await this.orm.call(
            "ahadu.calendar.view",
            "get_calendar_data",
            [this.state.year]
        );
        this.state.calendarData = data;
       
    }

    async onPreviousYear() {
        this.state.year--;
        await this.fetchCalendarData();
    }

    async onNextYear() {
        this.state.year++;
        await this.fetchCalendarData();
    }

    async onToday() {
        this.state.year = new Date().getFullYear();
        await this.fetchCalendarData();
    }
}

registry.category("actions").add("ahadu_calendar_view_tag", AhaduCalendarView);