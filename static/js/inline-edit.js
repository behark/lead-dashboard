/**
 * Inline Editing and Modal Lead Details
 * Edit lead info without leaving the page
 */

class InlineEditor {
    constructor() {
        this.currentLead = null;
        this.modal = null;
        this.init();
    }
    
    init() {
        // Create modal HTML
        this.createModal();
        
        // Add event listeners
        document.addEventListener('click', (e) => {
            // Double-click on lead card to edit
            const card = e.target.closest('.lead-card, tr[data-lead-id]');
            if (card && e.detail === 2) { // Double-click
                const leadId = parseInt(card.dataset.leadId);
                this.openEditModal(leadId);
            }
        });
    }
    
    createModal() {
        const modalHTML = `
            <div class="modal fade" id="quickEditModal" tabindex="-1">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">
                                <i class="bi bi-pencil-square"></i> Quick Edit Lead
                            </h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div id="quickEditContent">
                                <div class="text-center py-4">
                                    <div class="spinner-border text-primary" role="status">
                                        <span class="visually-hidden">Loading...</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-primary" id="saveQuickEdit">
                                <i class="bi bi-check-lg"></i> Save Changes
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        this.modal = new bootstrap.Modal(document.getElementById('quickEditModal'));
        
        // Save button handler
        document.getElementById('saveQuickEdit').addEventListener('click', () => {
            this.saveChanges();
        });
    }
    
    async openEditModal(leadId) {
        this.currentLead = leadId;
        
        // Show modal with loading state
        this.modal.show();
        
        // Fetch lead data
        try {
            const response = await fetch(`/api/lead/${leadId}`);
            const lead = await response.json();
            
            // Populate form
            this.renderEditForm(lead);
        } catch (error) {
            console.error('Error loading lead:', error);
            document.getElementById('quickEditContent').innerHTML = `
                <div class="alert alert-danger">
                    Failed to load lead data. Please try again.
                </div>
            `;
        }
    }
    
    renderEditForm(lead) {
        const content = `
            <div class="row g-3">
                <div class="col-md-6">
                    <label class="form-label fw-bold">Name</label>
                    <input type="text" class="form-control" id="edit_name" value="${lead.name || ''}" readonly>
                </div>
                <div class="col-md-6">
                    <label class="form-label fw-bold">Phone</label>
                    <input type="text" class="form-control" id="edit_phone" value="${lead.phone || ''}" readonly>
                </div>
                <div class="col-md-6">
                    <label class="form-label fw-bold">Status</label>
                    <select class="form-select" id="edit_status">
                        <option value="NEW" ${lead.status === 'NEW' ? 'selected' : ''}>NEW</option>
                        <option value="CONTACTED" ${lead.status === 'CONTACTED' ? 'selected' : ''}>CONTACTED</option>
                        <option value="REPLIED" ${lead.status === 'REPLIED' ? 'selected' : ''}>REPLIED</option>
                        <option value="CLOSED" ${lead.status === 'CLOSED' ? 'selected' : ''}>CLOSED</option>
                        <option value="LOST" ${lead.status === 'LOST' ? 'selected' : ''}>LOST</option>
                    </select>
                </div>
                <div class="col-md-6">
                    <label class="form-label fw-bold">Next Follow-up</label>
                    <input type="datetime-local" class="form-control" id="edit_followup" 
                           value="${lead.next_followup ? lead.next_followup.substring(0, 16) : ''}">
                </div>
                <div class="col-12">
                    <label class="form-label fw-bold">Notes</label>
                    <textarea class="form-control" id="edit_notes" rows="4">${lead.notes || ''}</textarea>
                </div>
                <div class="col-12">
                    <div class="d-flex gap-2 flex-wrap">
                        <span class="badge bg-primary">Score: ${lead.lead_score}</span>
                        <span class="badge ${lead.temperature === 'HOT' ? 'bg-danger' : lead.temperature === 'WARM' ? 'bg-warning text-dark' : 'bg-info'}">
                            ${lead.temperature}
                        </span>
                        <span class="badge bg-secondary">${lead.category}</span>
                        <span class="badge bg-info">${lead.city}, ${lead.country}</span>
                    </div>
                </div>
                ${lead.whatsapp_link ? `
                <div class="col-12">
                    <a href="${lead.whatsapp_link}" target="_blank" class="btn btn-success w-100">
                        <i class="bi bi-whatsapp"></i> Open WhatsApp
                    </a>
                </div>
                ` : ''}
            </div>
        `;
        
        document.getElementById('quickEditContent').innerHTML = content;
    }
    
    async saveChanges() {
        if (!this.currentLead) return;
        
        const data = {
            status: document.getElementById('edit_status').value,
            notes: document.getElementById('edit_notes').value,
            next_followup: document.getElementById('edit_followup').value
        };
        
        // Show saving state
        const saveBtn = document.getElementById('saveQuickEdit');
        const originalText = saveBtn.innerHTML;
        saveBtn.disabled = true;
        saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Saving...';
        
        try {
            const response = await fetch(`/lead/${this.currentLead}/update`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: new URLSearchParams(data)
            });
            
            const result = await response.json();
            
            if (result.success) {
                // Show success message
                this.showNotification('Changes saved successfully!', 'success');
                
                // Close modal
                this.modal.hide();
                
                // Refresh the page or update the card
                setTimeout(() => {
                    location.reload();
                }, 500);
            } else {
                throw new Error('Save failed');
            }
        } catch (error) {
            console.error('Error saving changes:', error);
            this.showNotification('Failed to save changes. Please try again.', 'danger');
            
            // Restore button
            saveBtn.disabled = false;
            saveBtn.innerHTML = originalText;
        }
    }
    
    showNotification(message, type) {
        const alert = document.createElement('div');
        alert.className = `alert alert-${type} alert-dismissible fade show`;
        alert.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
            min-width: 300px;
        `;
        alert.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        document.body.appendChild(alert);
        
        setTimeout(() => {
            alert.remove();
        }, 3000);
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    window.inlineEditor = new InlineEditor();
});

// Add API endpoint for getting single lead
// This should be added to routes/main.py:
/*
@main_bp.route('/api/lead/<int:lead_id>')
@login_required
def get_lead_api(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    return jsonify({
        'id': lead.id,
        'name': lead.name,
        'phone': lead.phone,
        'email': lead.email,
        'city': lead.city,
        'country': lead.country,
        'category': lead.category,
        'status': lead.status.value,
        'temperature': lead.temperature.value,
        'lead_score': lead.lead_score,
        'notes': lead.notes,
        'next_followup': lead.next_followup.isoformat() if lead.next_followup else None,
        'whatsapp_link': lead.whatsapp_link
    })
*/
