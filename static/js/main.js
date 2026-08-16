document.addEventListener('DOMContentLoaded', () => {
    document.body.classList.add('page-loaded');

    initializeCourseSearch();
    initializeSmoothScroll();
    initializeActiveNav();
    initializeLoginValidation();
    initializeVisualToggles();
    initializeOutlineCollapse();
});

// The outline is a sticky column on wide screens, where it should always be
// open. Below that it collapses into a strip above the reading column, and
// starting it closed keeps the content in view instead of pushing it down.
function initializeOutlineCollapse() {
    const outline = document.querySelector('.outline-collapse');

    if (!outline) {
        return;
    }

    const applyState = () => {
        outline.open = window.matchMedia('(min-width: 1201px)').matches;
    };

    applyState();
    window.addEventListener('resize', applyState);
}

// Diagrams are rendered server-side and are already in the DOM, so they are
// visible with JavaScript disabled. This only adds the ability to collapse one.
function initializeVisualToggles() {
    const toggles = document.querySelectorAll('[data-visual-toggle]');

    toggles.forEach((toggle) => {
        const panel = toggle.closest('[data-visual]');
        const body = panel ? panel.querySelector('[data-visual-body]') : null;

        if (!body) {
            return;
        }

        toggle.addEventListener('click', () => {
            const isOpen = toggle.getAttribute('aria-expanded') === 'true';
            toggle.setAttribute('aria-expanded', String(!isOpen));
            body.hidden = isOpen;
            toggle.textContent = isOpen ? 'Show diagram' : 'Hide diagram';
        });
    });
}

function initializeCourseSearch() {
    const searchInput = document.getElementById('courseSearch');
    const courseCards = document.querySelectorAll('.searchable-course');
    const noResultsMessage = document.getElementById('noResultsMessage');

    if (!searchInput || !courseCards.length) {
        return;
    }

    const filterCourses = () => {
        const query = searchInput.value.trim().toLowerCase();
        let visibleCount = 0;

        courseCards.forEach((card) => {
            const searchableText = (card.dataset.search || card.textContent).toLowerCase();
            const isVisible = searchableText.includes(query);
            card.style.display = isVisible ? '' : 'none';
            if (isVisible) {
                visibleCount += 1;
            }
        });

        if (noResultsMessage) {
            noResultsMessage.hidden = visibleCount !== 0;
        }
    };

    searchInput.addEventListener('input', filterCourses);
}

function initializeSmoothScroll() {
    const hashLinks = document.querySelectorAll('a[href^="#"]');

    hashLinks.forEach((link) => {
        link.addEventListener('click', (event) => {
            const targetId = link.getAttribute('href');
            const targetElement = targetId ? document.querySelector(targetId) : null;

            if (!targetElement) {
                return;
            }

            event.preventDefault();
            targetElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
    });
}

function initializeActiveNav() {
    const navLinks = document.querySelectorAll('.nav-links a');
    const currentPath = window.location.pathname.replace(/\/+$/, '') || '/';

    navLinks.forEach((link) => {
        const linkPath = new URL(link.href).pathname.replace(/\/+$/, '') || '/';
        if (linkPath === currentPath) {
            link.classList.add('active');
        }
    });
}

function initializeLoginValidation() {
    const loginForm = document.getElementById('loginForm');
    const message = document.getElementById('formMessage');

    if (!loginForm || !message) {
        return;
    }

    loginForm.addEventListener('submit', (event) => {
        event.preventDefault();

        const emailField = document.getElementById('email');
        const passwordField = document.getElementById('password');
        const emailValue = emailField ? emailField.value.trim() : '';
        const passwordValue = passwordField ? passwordField.value : '';
        const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

        message.classList.remove('success');

        if (!emailPattern.test(emailValue)) {
            message.textContent = 'Please enter a valid email address.';
            return;
        }

        if (passwordValue.length < 6) {
            message.textContent = 'Password must be at least 6 characters long.';
            return;
        }

        message.textContent = 'Login validation passed. Connect this form to your backend authentication flow.';
        message.classList.add('success');
    });
}
