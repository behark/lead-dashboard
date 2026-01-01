/**
 * Browser Notifications for Hot Leads
 * Requests permission and shows desktop notifications
 */

class LeadNotifications {
    constructor() {
        this.permission = 'default';
        this.checkInterval = 5 * 60 * 1000; // Check every 5 minutes
        this.lastCheck = Date.now();
        
        this.init();
    }
    
    async init() {
        // Check if notifications are supported
        if (!('Notification' in window)) {
            console.log('Browser notifications not supported');
            return;
        }
        
        // Request permission if not already granted
        if (Notification.permission === 'default') {
            await this.requestPermission();
        } else {
            this.permission = Notification.permission;
        }
        
        // Start checking for new hot leads
        if (this.permission === 'granted') {
            this.startChecking();
        }
    }
    
    async requestPermission() {
        try {
            const permission = await Notification.requestPermission();
            this.permission = permission;
            
            if (permission === 'granted') {
                this.showWelcomeNotification();
            }
        } catch (error) {
            console.error('Error requesting notification permission:', error);
        }
    }
    
    showWelcomeNotification() {
        new Notification('🔥 Hot Lead Alerts Enabled!', {
            body: 'You\'ll be notified when new hot leads arrive.',
            icon: '/static/icon-192.png',
            badge: '/static/badge-72.png',
            tag: 'welcome',
            requireInteraction: false
        });
    }
    
    startChecking() {
        // Check immediately
        this.checkForHotLeads();
        
        // Then check periodically
        setInterval(() => {
            this.checkForHotLeads();
        }, this.checkInterval);
    }
    
    async checkForHotLeads() {
        try {
            const response = await fetch('/api/hot-leads?since=' + this.lastCheck);
            const data = await response.json();
            
            if (data.leads && data.leads.length > 0) {
                data.leads.forEach(lead => {
                    this.showLeadNotification(lead);
                });
            }
            
            this.lastCheck = Date.now();
        } catch (error) {
            console.error('Error checking for hot leads:', error);
        }
    }
    
    showLeadNotification(lead) {
        const notification = new Notification(`🔥 New Hot Lead: ${lead.name}`, {
            body: `${lead.category} in ${lead.city}\nScore: ${lead.lead_score}\nPhone: ${lead.phone}`,
            icon: '/static/icon-192.png',
            badge: '/static/badge-72.png',
            tag: `lead-${lead.id}`,
            requireInteraction: true,
            data: {
                leadId: lead.id,
                url: `/lead/${lead.id}`
            },
            actions: [
                {
                    action: 'view',
                    title: '👁️ View Lead'
                },
                {
                    action: 'whatsapp',
                    title: '📱 WhatsApp'
                }
            ]
        });
        
        notification.onclick = (event) => {
            event.preventDefault();
            window.focus();
            window.location.href = notification.data.url;
            notification.close();
        };
    }
    
    // Manual trigger for testing
    testNotification() {
        if (this.permission !== 'granted') {
            alert('Please enable notifications first');
            return;
        }
        
        this.showLeadNotification({
            id: 1,
            name: 'Test Business',
            category: 'Restaurant',
            city: 'Pristina',
            lead_score: 95,
            phone: '+383 44 123 456'
        });
    }
}

// Initialize
const leadNotifications = new LeadNotifications();

// Add notification toggle to UI
document.addEventListener('DOMContentLoaded', () => {
    // Add notification button to sidebar if not exists
    const sidebar = document.querySelector('.sidebar nav');
    if (sidebar && Notification.permission !== 'granted') {
        const notifBtn = document.createElement('a');
        notifBtn.className = 'nav-link';
        notifBtn.href = '#';
        notifBtn.innerHTML = '<i class="bi bi-bell"></i> Enable Notifications';
        notifBtn.onclick = async (e) => {
            e.preventDefault();
            await leadNotifications.requestPermission();
            if (Notification.permission === 'granted') {
                notifBtn.remove();
            }
        };
        sidebar.appendChild(notifBtn);
    }
});

// Export for global access
window.leadNotifications = leadNotifications;
