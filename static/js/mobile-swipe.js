/**
 * Mobile Swipe Actions for Lead Cards
 * Swipe right = WhatsApp
 * Swipe left = Skip/Archive
 */

class SwipeHandler {
    constructor() {
        this.startX = 0;
        this.startY = 0;
        this.currentX = 0;
        this.currentY = 0;
        this.isDragging = false;
        this.threshold = 100; // pixels to trigger action
        
        this.init();
    }
    
    init() {
        // Only enable on touch devices
        if (!('ontouchstart' in window)) return;
        
        document.addEventListener('touchstart', this.handleTouchStart.bind(this), { passive: true });
        document.addEventListener('touchmove', this.handleTouchMove.bind(this), { passive: false });
        document.addEventListener('touchend', this.handleTouchEnd.bind(this), { passive: true });
    }
    
    handleTouchStart(e) {
        const target = e.target.closest('.lead-card, tr[data-lead-id]');
        if (!target) return;
        
        this.currentCard = target;
        this.startX = e.touches[0].clientX;
        this.startY = e.touches[0].clientY;
        this.isDragging = true;
        
        // Add transition class
        target.style.transition = 'none';
    }
    
    handleTouchMove(e) {
        if (!this.isDragging || !this.currentCard) return;
        
        this.currentX = e.touches[0].clientX;
        this.currentY = e.touches[0].clientY;
        
        const deltaX = this.currentX - this.startX;
        const deltaY = this.currentY - this.startY;
        
        // Only swipe horizontally if horizontal movement is dominant
        if (Math.abs(deltaX) > Math.abs(deltaY)) {
            e.preventDefault(); // Prevent scrolling
            
            // Apply transform
            this.currentCard.style.transform = `translateX(${deltaX}px)`;
            
            // Show action hint
            if (deltaX > 50) {
                this.currentCard.style.background = 'rgba(37, 211, 102, 0.2)'; // WhatsApp green
            } else if (deltaX < -50) {
                this.currentCard.style.background = 'rgba(108, 117, 125, 0.2)'; // Gray
            } else {
                this.currentCard.style.background = '';
            }
        }
    }
    
    handleTouchEnd(e) {
        if (!this.isDragging || !this.currentCard) return;
        
        const deltaX = this.currentX - this.startX;
        
        // Reset styles
        this.currentCard.style.transition = 'all 0.3s ease';
        this.currentCard.style.transform = '';
        this.currentCard.style.background = '';
        
        // Trigger action if threshold met
        if (Math.abs(deltaX) > this.threshold) {
            const leadId = parseInt(this.currentCard.dataset.leadId);
            
            if (deltaX > 0) {
                // Swipe right = WhatsApp
                this.triggerWhatsApp(leadId);
            } else {
                // Swipe left = Skip
                this.triggerSkip(leadId);
            }
        }
        
        // Reset state
        this.isDragging = false;
        this.currentCard = null;
        this.startX = 0;
        this.startY = 0;
        this.currentX = 0;
        this.currentY = 0;
    }
    
    triggerWhatsApp(leadId) {
        const card = document.querySelector(`[data-lead-id="${leadId}"]`);
        const whatsappBtn = card.querySelector('.btn-success');
        if (whatsappBtn) {
            whatsappBtn.click();
            this.showFeedback('📱 Opening WhatsApp...', 'success');
        }
    }
    
    triggerSkip(leadId) {
        if (typeof moveToNextLead === 'function') {
            moveToNextLead();
            this.showFeedback('⏭️ Skipped', 'info');
        }
    }
    
    showFeedback(message, type) {
        const feedback = document.createElement('div');
        feedback.className = `swipe-feedback swipe-${type}`;
        feedback.textContent = message;
        feedback.style.cssText = `
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: ${type === 'success' ? '#25D366' : '#6c757d'};
            color: white;
            padding: 15px 30px;
            border-radius: 10px;
            font-size: 1.2rem;
            font-weight: bold;
            z-index: 9999;
            animation: fadeInOut 1s ease;
        `;
        
        document.body.appendChild(feedback);
        
        setTimeout(() => {
            feedback.remove();
        }, 1000);
    }
}

// Initialize on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        new SwipeHandler();
    });
} else {
    new SwipeHandler();
}

// Add animation CSS
const swipeStyle = document.createElement('style');
swipeStyle.textContent = `
    @keyframes fadeInOut {
        0% { opacity: 0; transform: translate(-50%, -50%) scale(0.8); }
        50% { opacity: 1; transform: translate(-50%, -50%) scale(1); }
        100% { opacity: 0; transform: translate(-50%, -50%) scale(0.8); }
    }
`;
document.head.appendChild(swipeStyle);
