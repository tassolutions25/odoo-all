// Use vanilla JS - jQuery $(function(){}) is unreliable in Odoo 18's module system
document.addEventListener("DOMContentLoaded", function () {
    // Use event delegation for the toggles to ensure they work even if 
    // Odoo's OWL framework dynamically re-renders the DOM after load.
    document.addEventListener("click", function (e) {
        // Login page password toggle
        var toggleBtn = e.target.closest("#rt_toggle_password");
        if (toggleBtn) {
            var passwordInput = document.getElementById("password");
            if (passwordInput) {
                var isPassword = passwordInput.getAttribute("type") === "password";
                passwordInput.setAttribute("type", isPassword ? "text" : "password");
                toggleBtn.classList.toggle("fa-eye", isPassword);
                toggleBtn.classList.toggle("fa-eye-slash", !isPassword);
            }
        }

        // Confirm password toggle (signup page)
        var confirmToggleBtn = e.target.closest("#rt_toggle_confirm_password");
        if (confirmToggleBtn) {
            var confirmInput = document.getElementById("confirm_password");
            if (confirmInput) {
                var isPassword = confirmInput.getAttribute("type") === "password";
                confirmInput.setAttribute("type", isPassword ? "text" : "password");
                confirmToggleBtn.classList.toggle("fa-eye", isPassword);
                confirmToggleBtn.classList.toggle("fa-eye-slash", !isPassword);
            }
        }
    });

    // CRITICAL FIX: The Odoo OWL user_switch component forces 'd-none' on the login form.
    // We forcefully remove it here to ensure the form is visible in our custom layout.
    const loginForm = document.querySelector('form.oe_login_form');
    if (loginForm) {
        loginForm.classList.remove('d-none');
        // A MutationObserver ensures if OWL hides it again we unhide it
        const observer = new MutationObserver(function (mutations) {
            if (loginForm.classList.contains('d-none')) {
                loginForm.classList.remove('d-none');
            }
        });
        observer.observe(loginForm, { attributes: true, attributeFilter: ['class'] });
    }
});