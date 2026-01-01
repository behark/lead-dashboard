/**
 * Button Fixes and Error Handling
 * Ensures all buttons work properly with better error handling
 */

// Global error handler
window.addEventListener('error', function(e) {
    console.error('JavaScript Error:', e.error);
    // Don't show alert for every error, just log it
});

// Add safety checks to all button functions
(function() {
    'use strict';
    
    // Fix: Quick WhatsApp button
    window.safeQuickWhatsApp = function() {
        try {
            if (typeof quickWhatsApp === 'function') {
                quickWhatsApp();
            } else if (typeof selectedLeadId !== 'undefined' && selectedLeadId) {
                const card = document.querySelector(`[data-lead-id="${selectedLeadId}"]`);
                if (card) {
                    const whatsappBtn = card.querySelector('.btn-success');
                    if (whatsappBtn) {
                        whatsappBtn.click();
                    } else {
                        showError('WhatsApp button not found for this lead');
                    }
                } else {
                    showError('Please select a lead first');
                }
            } else {
                showError('Please select a lead first (click on a card)');
            }
        } catch (error) {
            console.error('Error in safeQuickWhatsApp:', error);
            showError('Error opening WhatsApp: ' + error.message);
        }
    };
    
    // Fix: Mark Contacted button
    window.safeMarkContacted = function() {
        try {
            if (typeof markContacted === 'function') {
                markContacted();
            } else if (typeof selectedLeadId !== 'undefined' && selectedLeadId) {
                quickContact(selectedLeadId);
            } else {
                showError('Please select a lead first');
            }
        } catch (error) {
            console.error('Error in safeMarkContacted:', error);
            showError('Error marking as contacted: ' + error.message);
        }
    };
    
    // Fix: Schedule Follow-up button
    window.safeScheduleFollowup = function() {
        try {
            if (typeof scheduleFollowup === 'function') {
                scheduleFollowup();
            } else {
                showError('Follow-up function not available');
            }
        } catch (error) {
            console.error('Error in safeScheduleFollowup:', error);
            showError('Error scheduling follow-up: ' + error.message);
        }
    };
    
    // Fix: Skip button
    window.safeSkipLead = function() {
        try {
            if (typeof skipLead === 'function') {
                skipLead();
            } else if (typeof moveToNextLead === 'function') {
                moveToNextLead();
            } else {
                showError('Skip function not available');
            }
        } catch (error) {
            console.error('Error in safeSkipLead:', error);
            showError('Error skipping lead: ' + error.message);
        }
    };
    
    // Fix: View toggle
    window.safeSwitchView = function(view) {
        try {
            if (typeof switchView === 'function') {
                switchView(view);
            } else {
                showError('View switch function not available');
            }
        } catch (error) {
            console.error('Error in safeSwitchView:', error);
            showError('Error switching view: ' + error.message);
        }
    };
    
    // Helper: Show error message
    function showError(message) {
        const alert = document.createElement('div');
        alert.className = 'alert alert-danger alert-dismissible fade show';
        alert.style.cssText = 'position: fixed; top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        alert.innerHTML = `
            <strong>Error:</strong> ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        document.body.appendChild(alert);
        
        setTimeout(() => {
            alert.remove();
        }, 5000);
    }
    
    // Helper: Show success message
    window.showSuccess = function(message) {
        const alert = document.createElement('div');
        alert.className = 'alert alert-success alert-dismissible fade show';
        alert.style.cssText = 'position: fixed; top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        alert.innerHTML = `
            <strong>Success:</strong> ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        document.body.appendChild(alert);
        
        setTimeout(() => {
            alert.remove();
        }, 3000);
    };
    
    // Fix: Validate phone numbers before generating WhatsApp links
    window.validateAndFixPhone = function(phone, country) {
        if (!phone) return null;
        
        // Remove all non-digits
        let clean = phone.replace(/\D/g, '');
        
        // Add country code if missing
        if (!clean.startsWith('383') && !clean.startsWith('355')) {
            if (country === 'Kosovo' || country === 'Kosova') {
                clean = '383' + clean.replace(/^0+/, '');
            } else if (country === 'Albania' || country === 'Shqipëri') {
                clean = '355' + clean.replace(/^0+/, '');
            }
        }
        
        // Validate length
        if (clean.length < 10 || clean.length > 15) {
            console.warn('Invalid phone number length:', clean);
            return null;
        }
        
        return '+' + clean;
    };
    
    // Fix: Ensure all WhatsApp links are valid
    document.addEventListener('DOMContentLoaded', function() {
        // Fix WhatsApp links
        document.querySelectorAll('a[href*="wa.me"]').forEach(link => {
            const href = link.getAttribute('href');
            if (!href || href === 'null' || href === 'undefined') {
                link.style.display = 'none';
                console.warn('Invalid WhatsApp link removed:', link);
            }
        });
        
        // Add click handlers to buttons with safety checks
        document.querySelectorAll('[onclick*="quickWhatsApp"]').forEach(btn => {
            const originalOnclick = btn.getAttribute('onclick');
            btn.removeAttribute('onclick');
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                safeQuickWhatsApp();
            });
        });
        
        document.querySelectorAll('[onclick*="markContacted"]').forEach(btn => {
            const originalOnclick = btn.getAttribute('onclick');
            btn.removeAttribute('onclick');
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                safeMarkContacted();
            });
        });
        
        // Fix preset buttons showing undefined
        document.querySelectorAll('.preset-btn .count').forEach(countEl => {
            if (countEl.textContent === 'undefined' || countEl.textContent === 'NaN') {
                countEl.textContent = '0';
            }
        });
        
        // Add loading indicators to all buttons
        document.querySelectorAll('button[type="submit"], .btn-primary, .btn-success').forEach(btn => {
            if (!btn.hasAttribute('data-loading-added')) {
                btn.setAttribute('data-loading-added', 'true');
                btn.addEventListener('click', function() {
                    if (this.type === 'submit' || this.classList.contains('btn-primary') || this.classList.contains('btn-success')) {
                        const originalHTML = this.innerHTML;
                        this.disabled = true;
                        this.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Loading...';
                        
                        // Re-enable after 5 seconds (failsafe)
                        setTimeout(() => {
                            this.disabled = false;
                            this.innerHTML = originalHTML;
                        }, 5000);
                    }
                });
            }
        });
        
        console.log('✅ Button fixes applied successfully');
    });
    
    // Fix: Handle AJAX errors gracefully
    const originalFetch = window.fetch;
    window.fetch = function(...args) {
        return originalFetch.apply(this, args)
            .then(response => {
                if (!response.ok) {
                    console.error('HTTP Error:', response.status, response.statusText);
                    if (response.status === 404) {
                        showError('Resource not found (404)');
                    } else if (response.status === 500) {
                        showError('Server error (500)');
                    } else if (response.status === 403) {
                        showError('Access denied (403)');
                    }
                }
                return response;
            })
            .catch(error => {
                console.error('Fetch Error:', error);
                showError('Network error: ' + error.message);
                throw error;
            });
    };
    
    // Debug mode: Log all button clicks
    if (window.location.search.includes('debug=true')) {
        document.addEventListener('click', function(e) {
            if (e.target.tagName === 'BUTTON' || e.target.closest('button')) {
                const btn = e.target.tagName === 'BUTTON' ? e.target : e.target.closest('button');
                console.log('Button clicked:', {
                    text: btn.textContent.trim(),
                    classes: btn.className,
                    onclick: btn.getAttribute('onclick'),
                    type: btn.type
                });
            }
        }, true);
    }
    
})();

// Export for testing
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        safeQuickWhatsApp,
        safeMarkContacted,
        safeScheduleFollowup,
        safeSkipLead,
        safeSwitchView,
        validateAndFixPhone
    };
}
