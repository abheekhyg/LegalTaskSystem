// Any additional JavaScript functionality can be added here
document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips if needed
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl)
    });
}); 