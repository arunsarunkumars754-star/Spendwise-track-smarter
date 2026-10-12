/**
 * SpendWise - Frontend Application Script
 * Handles Theme Toggling, Mobile Sidebar, Interactive Charts, and UX Enhancements.
 */

// Theme Management
(function () {
    const themeStorageKey = 'spendwise_theme';
    const defaultTheme = 'light';

    function getPreferredTheme() {
        const storedTheme = localStorage.getItem(themeStorageKey);
        if (storedTheme) {
            return storedTheme;
        }
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : defaultTheme;
    }

    function applyTheme(theme) {
        document.documentElement.setAttribute('data-bs-theme', theme);
        localStorage.setItem(themeStorageKey, theme);

        const themeToggleBtn = document.getElementById('theme-toggle-btn');
        if (themeToggleBtn) {
            const icon = themeToggleBtn.querySelector('i');
            if (icon) {
                if (theme === 'dark') {
                    icon.className = 'bi bi-sun-fill text-warning';
                    themeToggleBtn.setAttribute('title', 'Switch to Light Mode');
                } else {
                    icon.className = 'bi bi-moon-stars-fill text-secondary';
                    themeToggleBtn.setAttribute('title', 'Switch to Dark Mode');
                }
            }
        }

        // Notify charts if any
        window.dispatchEvent(new CustomEvent('themeChanged', { detail: { theme: theme } }));
    }

    // Initialize theme immediately
    applyTheme(getPreferredTheme());

    document.addEventListener('DOMContentLoaded', () => {
        const themeToggleBtn = document.getElementById('theme-toggle-btn');
        if (themeToggleBtn) {
            themeToggleBtn.addEventListener('click', () => {
                const currentTheme = document.documentElement.getAttribute('data-bs-theme') || 'light';
                const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
                applyTheme(newTheme);
            });
        }

        // Mobile Sidebar Drawer Toggle
        const sidebarToggle = document.getElementById('sidebar-toggle');
        const sidebar = document.querySelector('.sidebar');
        const backdrop = document.getElementById('sidebar-backdrop');

        if (sidebarToggle && sidebar && backdrop) {
            sidebarToggle.addEventListener('click', () => {
                sidebar.classList.toggle('show');
                backdrop.classList.toggle('show');
            });

            backdrop.addEventListener('click', () => {
                sidebar.classList.remove('show');
                backdrop.classList.remove('show');
            });
        }

        // Auto-filter category dropdown based on transaction type selector
        const typeSelect = document.getElementById('id_transaction_type');
        const categorySelect = document.getElementById('id_category');

        if (typeSelect && categorySelect) {
            function updateCategoryOptions() {
                const selectedType = typeSelect.value;
                const options = categorySelect.querySelectorAll('option');

                options.forEach(opt => {
                    if (!opt.value) return; // Keep placeholder option visible
                    const text = opt.textContent;
                    // Check if category type tag is embedded or matches
                    if (opt.dataset && opt.dataset.type) {
                        if (opt.dataset.type === selectedType) {
                            opt.hidden = false;
                        } else {
                            opt.hidden = true;
                            if (categorySelect.value === opt.value) {
                                categorySelect.value = '';
                            }
                        }
                    }
                });
            }

            typeSelect.addEventListener('change', updateCategoryOptions);
        }

        // Auto-dismiss alert messages after 5 seconds
        const alerts = document.querySelectorAll('.alert-dismissible');
        alerts.forEach(alert => {
            setTimeout(() => {
                try {
                    const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
                    if (bsAlert) bsAlert.close();
                } catch (e) {}
            }, 6000);
        });
    });
})();
