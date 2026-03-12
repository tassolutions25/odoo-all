odoo.define('ahadu_website_custom.disable_apply_script', function (require) {
    'use strict';

    const publicWidget = require('web.public.widget');

    publicWidget.registry.AhaduJobApply = publicWidget.Widget.extend({
        selector: '#hr_recruitment_form',
        start: function () {
            const form = this.$el[0];
            if (!form) return;

            // Ensure we are on job pages only
            const path = window.location.pathname;
            if (!(path.startsWith('/jobs') || path.includes('/apply'))) return;

            // Remove Odoo-specific data attributes and listeners
            form.removeAttribute('data-job-id');
            form.removeAttribute('data-ajax');
            form.onsubmit = null;

            // Set the custom action
            form.action = '/ahadu/jobs/apply_custom';

            // Clone the node to remove any inline listeners
            const clone = form.cloneNode(true);
            form.parentNode.replaceChild(clone, form);

            // Handle form submission via AJAX
            clone.addEventListener('submit', function (e) {
                e.preventDefault();
                const formData = new FormData(clone);

                fetch(clone.action, {
                    method: 'POST',
                    body: formData
                })
                    .then(res => res.json())
                    .then(data => {
                        if (data.success && data.redirect) {
                            window.location.href = data.redirect;
                        } else if (data.error) {
                            alert('Error: ' + data.error);
                        }
                    })
                    .catch(err => {
                        console.error('[Ahadu] Form submission failed:', err);
                        alert('An error has occurred. The form has not been sent.');
                    });
            });

            console.log('[Ahadu] Job form neutralized, custom action set.');
        }
    });
});



