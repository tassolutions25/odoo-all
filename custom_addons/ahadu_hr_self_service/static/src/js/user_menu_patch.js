/** @odoo-module **/

import { registry } from "@web/core/registry";

// Get the user menu items registry collection
const userMenuRegistry = registry.category("user_menuitems");

// Safely remove "My Profile" so it is not rendered in the user dropdown list
if (userMenuRegistry.contains("profile")) {
    userMenuRegistry.remove("profile");
}