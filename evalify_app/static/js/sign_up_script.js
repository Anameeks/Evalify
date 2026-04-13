// static/js/sign_up_script.js

document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const form = document.querySelector('form');
    const nameField = document.getElementById('profileName') || document.querySelector('input[name="full_name"]');
    const emailField = document.querySelector('input[name="email"]');
    const passwordField = document.getElementById('passwordField');
    const strengthText = document.getElementById('passwordStrength');
    const roleRadios = document.querySelectorAll('input[name="role"]');
    const togglePass = document.getElementById('togglePass');

    // Create dynamic error container (if not exists)
    let errorContainer = document.querySelector('.email-error');
    if (!errorContainer) {
        errorContainer = document.createElement('div');
        errorContainer.className = 'email-error';
        errorContainer.style.cssText = 'background:rgba(255,80,80,0.15);border:1px solid rgba(255,80,80,0.3);border-radius:8px;padding:12px 16px;margin-bottom:16px;color:#ff6b6b;font-size:14px;display:none;';
        const firstInput = document.querySelector('.input-group');
        if (firstInput) firstInput.parentNode.insertBefore(errorContainer, firstInput);
    }

    /* ========== PASSWORD SHOW/HIDE ========== */
    if (togglePass) {
        togglePass.addEventListener('click', function() {
            if (passwordField.type === "password") {
                passwordField.type = "text";
                this.textContent = "👁 Show";
            } else {
                passwordField.type = "password";
                this.textContent = "👁 Hide";
            }
        });
    }

    /* ========== PASSWORD STRENGTH ========== */
    if (passwordField && strengthText) {
        passwordField.addEventListener("input", function() {
            let value = passwordField.value;
            let strength = 0;
            if (value.length >= 8) strength++;
            if (value.match(/[a-z]/)) strength++;
            if (value.match(/[A-Z]/)) strength++;
            if (value.match(/[0-9]/)) strength++;
            if (value.match(/[^a-zA-Z0-9]/)) strength++;

            switch(strength) {
                case 0: case 1: case 2:
                    strengthText.textContent = "Weak Password";
                    strengthText.style.color = "red";
                    break;
                case 3:
                    strengthText.textContent = "Medium Password";
                    strengthText.style.color = "orange";
                    break;
                case 4:
                    strengthText.textContent = "Strong Password";
                    strengthText.style.color = "lime";
                    break;
                case 5:
                    strengthText.textContent = "Very Strong Password";
                    strengthText.style.color = "cyan";
                    break;
            }
        });
    }

    /* ========== EMAIL VALIDATION BASED ON ROLE ========== */
    function validateEmailByRole(email, role) {
        if (role === 'student') {
            const studentPattern = /^\d+@uap-bd\.edu$/;
            return studentPattern.test(email);
        } else if (role === 'faculty') {
            const facultyPattern = /^[A-Za-z][A-Za-z0-9._]*@uap-bd\.edu$/;
            return facultyPattern.test(email);
        }
        return false;
    }

    function getSelectedRole() {
        for (let radio of roleRadios) {
            if (radio.checked) return radio.value;
        }
        return null;
    }

    // Optional: Real-time email validation when role or email changes
    emailField.addEventListener('input', function() {
        const role = getSelectedRole();
        if (role && emailField.value.trim() !== '') {
            if (!validateEmailByRole(emailField.value.trim(), role)) {
                emailField.style.borderColor = '#ff6b6b';
            } else {
                emailField.style.borderColor = '#4caf50';
            }
        } else {
            emailField.style.borderColor = '';
        }
    });

    roleRadios.forEach(radio => {
        radio.addEventListener('change', function() {
            if (emailField.value.trim() !== '') {
                const role = getSelectedRole();
                if (!validateEmailByRole(emailField.value.trim(), role)) {
                    emailField.style.borderColor = '#ff6b6b';
                } else {
                    emailField.style.borderColor = '#4caf50';
                }
            }
        });
    });

    /* ========== FORM SUBMIT VALIDATION ========== */
    form.addEventListener("submit", function(e) {
        let name = nameField ? nameField.value.trim() : '';
        let email = emailField.value.trim();
        let password = passwordField.value.trim();
        let role = getSelectedRole();

        // Basic validations
        if (name === "") {
            alert("Profile Name is required");
            e.preventDefault();
            return;
        }

        if (email === "") {
            alert("Email is required");
            e.preventDefault();
            return;
        }

        let emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailPattern.test(email)) {
            alert("Invalid email format");
            e.preventDefault();
            return;
        }

        if (password.length < 8) {
            alert("Password must be at least 8 characters");
            e.preventDefault();
            return;
        }

        if (!role) {
            alert("Please select Student or Faculty");
            e.preventDefault();
            return;
        }

        // Role-based email domain validation
        if (!validateEmailByRole(email, role)) {
            if (role === 'student') {
                alert("Student email must be digits@uap-bd.edu (e.g., 20241001@uap-bd.edu)");
            } else {
                alert("Faculty email must be name@uap-bd.edu (e.g., john.doe@uap-bd.edu)");
            }
            e.preventDefault();
            return;
        }

        // If all valid, form submits normally
    });
});