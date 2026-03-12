(function () {
    "use strict";

    console.log("[Ahadu Job Fix v5 FINAL] Script loaded. This version will stop event propagation.");

    const FORM_ID = "custom_hr_recruitment_form";
    const BUTTON_ID = "custom_submit_button";
    const SUBMIT_URL = "/ahadu/jobs/apply_custom";

    function initializeFinalSubmit() {
        const form = document.getElementById(FORM_ID);
        const button = document.getElementById(BUTTON_ID);

        if (!form || !button) {
            console.error("[Ahadu Job Fix v5] Did not find the form or button. Check template IDs.");
            return;
        }

        console.log("[Ahadu Job Fix v5] Found form and button. Attaching the final click handler.");

        button.addEventListener('click', function (event) {
            event.preventDefault();   // ✅ blocks default form submission
            event.stopPropagation();
            form.addEventListener('submit', (e) => e.preventDefault(), true);

            console.log("[Ahadu Job Fix v5] Click handled and propagation stopped. Starting our submission.");

// Check for HTML5 validation errors
if (typeof form.checkValidity === 'function' && !form.checkValidity()) {
    form.reportValidity();
    return;
}

// ✅ File type validation (PDF, PNG, JPEG only)
const fileInput = document.getElementById("application_documents");
if (fileInput && fileInput.files.length > 0) {
    const allowedTypes = ["application/pdf", "image/png", "image/jpeg"];
    for (let file of fileInput.files) {
        if (!allowedTypes.includes(file.type)) {
            alert(`❌ Invalid file type: ${file.name}\n\nOnly PDF, PNG, and JPEG files are allowed.`);
            return; // ⛔ stop submission
        }
    }
}

const spinner = document.getElementById('o_website_form_loading');

button.disabled = true;
if (spinner) spinner.classList.remove('d-none');

const formData = new FormData(form);


            fetch(SUBMIT_URL, {
                method: 'POST',
                body: formData,
            })
            .then(response => {
                if (response.redirected) {
                    window.location.href = response.url;
                    return null;
                }
                if (!response.ok) {
                    return response.json().catch(() => {
                        throw new Error(`Server Error: Status ${response.status}.`);
                    });
                }
                return response.json();
            })
            .then(data => {
                if (!data) return; // Already handled by redirect
                if (data.error) {
                    alert('Error: ' + data.error);
                } else {
                    alert('An unexpected error occurred.');
                }
            })
            .catch(error => {
                console.error('[Ahadu Job Fix v5] Submission failed:', error);
                alert(error.message);
            })
            .finally(() => {
                button.disabled = false;
                if (spinner) spinner.classList.add('d-none');
            });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeFinalSubmit);
    } else {
        initializeFinalSubmit();
    }
})();