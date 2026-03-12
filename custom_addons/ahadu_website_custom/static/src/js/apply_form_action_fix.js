/** @odoo-module **/

import { registry } from "@web/core/registry";

registry.category("public_root").add("ahadu_apply_form_fix", {
    start() {
        window.addEventListener("load", function () {
            const form = document.getElementById("hr_recruitment_form");
            if (!form) return;

            const cleanAction = "/ahadu/jobs/apply_custom";

            // Remove Odoo’s ajax and data handlers if any
            form.removeAttribute("data-ajax");
            form.removeEventListener("submit", form.onsubmit);
            form.onsubmit = null;

            // Detach all jQuery event handlers (if jQuery exists)
            if (window.$) {
                try {
                    $(form).off("submit");
                } catch (err) {
                    console.warn("[Ahadu Fix] jQuery off error:", err);
                }
            }

            // Force clean action
            form.setAttribute("action", cleanAction);

            // Intercept submit and handle via AJAX with redirect
            form.addEventListener(
                "submit",
                function (e) {
                    e.preventDefault(); // prevent normal submit
                    const current = form.getAttribute("action") || cleanAction;

                    // Handle misconfigured action
                    if (current.includes("undefined")) {
                        form.setAttribute("action", cleanAction);
                        console.warn("[Ahadu Fix] Reset bad form action to:", cleanAction);
                    }

                    const formData = new FormData(form);

                    fetch(current, {
                        method: "POST",
                        body: formData,
                    })
                        .then((res) => res.json())
                        .then((data) => {
                            if (data.success && data.redirect) {
                                window.location.href = data.redirect; // ✅ redirect to thank-you page
                            } else if (data.error) {
                                alert("Error: " + data.error);
                            }
                        })
                        .catch((err) => {
                            console.error("[Ahadu Fix] Form submission failed:", err);
                        });
                },
                true
            );

            console.info("[Ahadu Fix] Recruitment form handler loaded.");
        });
    },
});

// Auto-correct form action if misconfigured
setInterval(() => {
    const form = document.getElementById("hr_recruitment_form");
    if (form && form.action.includes("undefined")) {
        form.action = "/ahadu/jobs/apply_custom";
        console.warn("[Ahadu Fix] Auto-corrected bad form action.");
    }
}, 500);
