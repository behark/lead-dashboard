"""
Business Dashboard Routes
Integrated dashboard showing all business metrics
Fully connected to both lead-dashboard and website-generator systems
"""

from flask import Blueprint, render_template_string, jsonify
from flask_login import login_required
from models import db, Lead, LeadStatus, LeadTemperature, ContactLog
from datetime import datetime, timezone, timedelta
from sqlalchemy import func
import sys
import os
import json
from pathlib import Path

business_dashboard_bp = Blueprint('business_dashboard', __name__, url_prefix='/business-dashboard')

# Add website-generator to path for tracking modules
sys.path.insert(0, '/home/behar/Desktop/website-generator')

# Import tracking modules with graceful fallback
TRACKING_AVAILABLE = False
tracker = None
payment_tracker = None
demo_stats_all = {}

try:
    from conversion_tracker import tracker
    from demo_analytics import get_all_stats
    from payment_tracker import payment_tracker
    from lead_scoring_dashboard import LeadScoringDashboard
    from performance_monitor import PerformanceMonitor
    TRACKING_AVAILABLE = True
    print("✅ Tracking modules loaded successfully")
except Exception as e:
    print(f"⚠️  Warning: Some tracking modules not available: {e}")
    # Create dummy classes for graceful degradation
    class DummyTracker:
        def get_funnel_stats(self):
            return {'funnel': {}, 'conversion_rates': {}}
    tracker = DummyTracker()

# Dashboard HTML Template
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Business Dashboard - Tracking & Analytics</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>📊</text></svg>">
    <script>
        // Suppress ALL console warnings before libraries load
        (function() {
            const originalWarn = console.warn;
            const originalError = console.error;
            console.warn = function(...args) {
                const msg = args[0] ? String(args[0]) : '';
                if (msg.includes('cdn.tailwindcss.com') || msg.includes('should not be used in production')) {
                    return; // Suppress Tailwind CDN warning
                }
                originalWarn.apply(console, args);
            };
            // Also suppress Chart.js animator violations (they're just warnings)
            console.error = function(...args) {
                const msg = args[0] ? String(args[0]) : '';
                if (msg.includes('Violation') && msg.includes('requestAnimationFrame')) {
                    return; // Suppress performance violations (they're just warnings)
                }
                originalError.apply(console, args);
            };
        })();
    </script>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        .gradient-bg { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
        .card-hover { transition: all 0.3s ease; will-change: transform; }
        .card-hover:hover { transform: translateY(-5px); box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1); }
        .pulse-dot { animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite; will-change: opacity; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: .5; } }
        @media (prefers-reduced-motion: reduce) {
            .card-hover, .pulse-dot { animation: none; }
        }
    </style>
</head>
<body class="bg-gray-50">
    <!-- Header -->
    <div class="gradient-bg text-white py-6 shadow-lg">
        <div class="container mx-auto px-4">
            <div class="flex items-center justify-between">
                <div>
                    <h1 class="text-3xl font-bold"><i class="fas fa-chart-line mr-2"></i>Business Dashboard</h1>
                    <p class="text-gray-200 mt-1">Real-time tracking & analytics - All platforms connected</p>
                </div>
                <a href="/" class="bg-white text-purple-600 px-4 py-2 rounded-lg hover:bg-gray-100">
                    <i class="fas fa-arrow-left mr-2"></i>Back to Leads
                </a>
            </div>
        </div>
    </div>

    <!-- Main Content -->
    <div class="container mx-auto px-4 py-8">
        <!-- Stats Cards -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <div class="bg-white rounded-lg shadow-md p-6 card-hover">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-gray-500 text-sm">Total Contacts</p>
                        <p class="text-3xl font-bold text-gray-800" id="total-contacts">0</p>
                        <p class="text-xs text-gray-400 mt-1" id="contacts-source">From database</p>
                    </div>
                    <div class="bg-blue-100 p-3 rounded-full">
                        <i class="fas fa-users text-blue-600 text-2xl"></i>
                    </div>
                </div>
            </div>

            <div class="bg-white rounded-lg shadow-md p-6 card-hover">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-gray-500 text-sm">Closed Deals</p>
                        <p class="text-3xl font-bold text-gray-800" id="closed-deals">0</p>
                        <p class="text-xs text-gray-400 mt-1" id="deals-source">From database</p>
                    </div>
                    <div class="bg-green-100 p-3 rounded-full">
                        <i class="fas fa-check-circle text-green-600 text-2xl"></i>
                    </div>
                </div>
            </div>

            <div class="bg-white rounded-lg shadow-md p-6 card-hover">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-gray-500 text-sm">Total Revenue</p>
                        <p class="text-3xl font-bold text-gray-800" id="total-revenue">€0</p>
                        <p class="text-xs text-gray-400 mt-1" id="revenue-source">From payment tracker</p>
                    </div>
                    <div class="bg-purple-100 p-3 rounded-full">
                        <i class="fas fa-euro-sign text-purple-600 text-2xl"></i>
                    </div>
                </div>
            </div>

            <div class="bg-white rounded-lg shadow-md p-6 card-hover">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-gray-500 text-sm">Hot Leads</p>
                        <p class="text-3xl font-bold text-gray-800" id="hot-leads">0</p>
                        <p class="text-xs text-gray-400 mt-1" id="hot-leads-source">From demo analytics</p>
                    </div>
                    <div class="bg-red-100 p-3 rounded-full">
                        <i class="fas fa-fire text-red-600 text-2xl"></i>
                    </div>
                </div>
            </div>
        </div>

        <!-- Charts Row -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
            <!-- Conversion Funnel -->
            <div class="bg-white rounded-lg shadow-md p-6">
                <h2 class="text-xl font-bold mb-4"><i class="fas fa-funnel-dollar mr-2"></i>Conversion Funnel</h2>
                <canvas id="funnelChart" height="300"></canvas>
            </div>

            <!-- Revenue Chart -->
            <div class="bg-white rounded-lg shadow-md p-6">
                <h2 class="text-xl font-bold mb-4"><i class="fas fa-chart-line mr-2"></i>Revenue Trend</h2>
                <canvas id="revenueChart" height="300"></canvas>
            </div>
        </div>

        <!-- Hot Leads & Recent Activity -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
            <!-- Hot Leads -->
            <div class="bg-white rounded-lg shadow-md p-6">
                <h2 class="text-xl font-bold mb-4"><i class="fas fa-fire mr-2 text-red-600"></i>Hot Leads</h2>
                <div id="hot-leads-list" class="space-y-3">
                    <p class="text-gray-500">Loading...</p>
                </div>
            </div>

            <!-- Recent Activity -->
            <div class="bg-white rounded-lg shadow-md p-6">
                <h2 class="text-xl font-bold mb-4"><i class="fas fa-clock mr-2"></i>Recent Activity</h2>
                <div id="recent-activity" class="space-y-3">
                    <p class="text-gray-500">Loading...</p>
                </div>
            </div>
        </div>

        <!-- Performance Metrics -->
        <div class="bg-white rounded-lg shadow-md p-6 mb-8">
            <h2 class="text-xl font-bold mb-4"><i class="fas fa-tachometer-alt mr-2"></i>Performance Metrics</h2>
            <div id="performance-metrics" class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <p class="text-gray-500">Loading...</p>
            </div>
        </div>

        <!-- Action Items -->
        <div class="bg-gradient-to-r from-yellow-400 to-orange-500 rounded-lg shadow-md p-6 text-white">
            <h2 class="text-xl font-bold mb-4"><i class="fas fa-tasks mr-2"></i>Action Items for Today</h2>
            <div id="action-items" class="space-y-2">
                <p>Loading...</p>
            </div>
        </div>

        <!-- Connection Status -->
        <div class="bg-white rounded-lg shadow-md p-6 mt-8">
            <h2 class="text-xl font-bold mb-4"><i class="fas fa-plug mr-2"></i>System Connections</h2>
            <div id="connection-status" class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div class="p-4 bg-green-50 rounded border-l-4 border-green-500">
                    <p class="font-bold text-green-800"><i class="fas fa-check-circle mr-2"></i>Lead Dashboard Database</p>
                    <p class="text-sm text-gray-600">Connected - Pulling lead data</p>
                </div>
                <div id="tracking-status" class="p-4 bg-blue-50 rounded border-l-4 border-blue-500">
                    <p class="font-bold text-blue-800"><i class="fas fa-check-circle mr-2"></i>Tracking System</p>
                    <p class="text-sm text-gray-600">Connected - Pulling analytics</p>
                </div>
            </div>
        </div>
    </div>

    <!-- JavaScript -->
    <script>
        let funnelChart, revenueChart;

        function loadDashboard() {
            fetch('/business-dashboard/api/data')
                .then(r => {
                    if (!r.ok) {
                        throw new Error('Failed to load dashboard data');
                    }
                    return r.json();
                })
                .then(data => {
                    // Update stats
                    document.getElementById('total-contacts').textContent = data.stats.total_contacts || 0;
                    document.getElementById('closed-deals').textContent = data.stats.closed_deals || 0;
                    document.getElementById('total-revenue').textContent = '€' + (data.stats.total_revenue || 0).toFixed(2);
                    document.getElementById('hot-leads').textContent = data.stats.hot_leads || 0;

                    // Update source indicators
                    if (data.sources) {
                        if (data.sources.contacts) {
                            document.getElementById('contacts-source').textContent = data.sources.contacts;
                        }
                        if (data.sources.deals) {
                            document.getElementById('deals-source').textContent = data.sources.deals;
                        }
                        if (data.sources.revenue) {
                            document.getElementById('revenue-source').textContent = data.sources.revenue;
                        }
                        if (data.sources.hot_leads) {
                            document.getElementById('hot-leads-source').textContent = data.sources.hot_leads;
                        }
                    }

                    // Update connection status
                    if (data.connections) {
                        updateConnectionStatus(data.connections);
                    }

                    // Update charts
                    updateFunnelChart(data.funnel);
                    updateRevenueChart(data.revenue);
                    updateHotLeads(data.hot_leads);
                    updateRecentActivity(data.activity);
                    updatePerformanceMetrics(data.performance);
                    updateActionItems(data.action_items);
                })
                .catch(e => {
                    console.error('Error loading dashboard:', e);
                    document.getElementById('hot-leads-list').innerHTML = 
                        '<p class="text-red-500">Error loading data. Please refresh the page.</p>';
                });
        }

        function updateConnectionStatus(connections) {
            const container = document.getElementById('tracking-status');
            if (connections.tracking_available) {
                container.className = 'p-4 bg-green-50 rounded border-l-4 border-green-500';
                container.innerHTML = `
                    <p class="font-bold text-green-800"><i class="fas fa-check-circle mr-2"></i>Tracking System</p>
                    <p class="text-sm text-gray-600">Connected - All modules active</p>
                `;
            } else {
                container.className = 'p-4 bg-yellow-50 rounded border-l-4 border-yellow-500';
                container.innerHTML = `
                    <p class="font-bold text-yellow-800"><i class="fas fa-exclamation-triangle mr-2"></i>Tracking System</p>
                    <p class="text-sm text-gray-600">Partial - Some modules unavailable</p>
                `;
            }
        }

        function updateFunnelChart(data) {
            const ctx = document.getElementById('funnelChart').getContext('2d');
            if (funnelChart) {
                funnelChart.destroy();
                funnelChart = null;
            }
            
            funnelChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: data.labels || [],
                    datasets: [{
                        label: 'Count',
                        data: data.values || [],
                        backgroundColor: ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'],
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: false,
                    animations: {
                        colors: false,
                        x: false,
                        y: false
                    },
                    scales: { 
                        y: { 
                            beginAtZero: true,
                            ticks: {
                                precision: 0
                            }
                        } 
                    },
                    plugins: {
                        legend: {
                            display: false
                        }
                    }
                }
            });
        }

        function updateRevenueChart(data) {
            const ctx = document.getElementById('revenueChart').getContext('2d');
            if (revenueChart) {
                revenueChart.destroy();
                revenueChart = null;
            }
            
            revenueChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.labels || [],
                    datasets: [{
                        label: 'Revenue (€)',
                        data: data.values || [],
                        borderColor: '#8b5cf6',
                        backgroundColor: 'rgba(139, 92, 246, 0.1)',
                        tension: 0.4,
                        fill: true
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: false,
                    animations: {
                        colors: false,
                        x: false,
                        y: false
                    },
                    scales: { 
                        y: { 
                            beginAtZero: true,
                            ticks: {
                                callback: function(value) {
                                    return '€' + value.toFixed(2);
                                }
                            }
                        } 
                    },
                    plugins: {
                        legend: {
                            display: false
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    return 'Revenue: €' + context.parsed.y.toFixed(2);
                                }
                            }
                        }
                    }
                }
            });
        }

        function updateHotLeads(leads) {
            const container = document.getElementById('hot-leads-list');
            if (!leads || leads.length === 0) {
                container.innerHTML = '<p class="text-gray-500">No hot leads yet</p>';
                return;
            }
            
            container.innerHTML = leads.map(lead => `
                <div class="border-l-4 border-red-500 pl-4 py-2 bg-red-50 rounded cursor-pointer hover:bg-red-100" onclick="window.location.href='/lead/${lead.id || ''}'">
                    <p class="font-bold text-gray-800">${lead.name}</p>
                    <p class="text-sm text-gray-600">Score: ${lead.score} | Views: ${lead.views} | Interactions: ${lead.interactions}</p>
                    ${lead.phone ? `<p class="text-xs text-gray-500 mt-1"><i class="fas fa-phone mr-1"></i>${lead.phone}</p>` : ''}
                </div>
            `).join('');
        }

        function updateRecentActivity(activities) {
            const container = document.getElementById('recent-activity');
            if (!activities || activities.length === 0) {
                container.innerHTML = '<p class="text-gray-500">No recent activity</p>';
                return;
            }
            
            container.innerHTML = activities.map(activity => `
                <div class="flex items-center space-x-3 py-2 border-b">
                    <div class="w-2 h-2 bg-blue-500 rounded-full pulse-dot"></div>
                    <div class="flex-1">
                        <p class="text-sm text-gray-800">${activity.text}</p>
                        <p class="text-xs text-gray-500">${activity.time}</p>
                    </div>
                </div>
            `).join('');
        }

        function updatePerformanceMetrics(metrics) {
            const container = document.getElementById('performance-metrics');
            if (!metrics) {
                container.innerHTML = '<p class="text-gray-500">No metrics available</p>';
                return;
            }
            
            container.innerHTML = metrics.map(metric => `
                <div class="p-4 bg-gray-50 rounded">
                    <p class="text-sm text-gray-600">${metric.label}</p>
                    <p class="text-2xl font-bold ${metric.on_target ? 'text-green-600' : 'text-red-600'}">${metric.value}</p>
                    <p class="text-xs text-gray-500">Target: ${metric.target}</p>
                </div>
            `).join('');
        }

        function updateActionItems(items) {
            const container = document.getElementById('action-items');
            if (!items || items.length === 0) {
                container.innerHTML = '<p>No action items. Keep up the great work!</p>';
                return;
            }
            
            container.innerHTML = items.map((item, i) => `
                <div class="flex items-center space-x-3 py-2">
                    <span class="text-2xl">${item.icon}</span>
                    <span>${item.text}</span>
                </div>
            `).join('');
        }

        // Load on page load (with debounce)
        let loadTimeout;
        function debouncedLoad() {
            clearTimeout(loadTimeout);
            loadTimeout = setTimeout(loadDashboard, 100);
        }
        
        // Initial load
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', debouncedLoad);
        } else {
            debouncedLoad();
        }
        
        // Auto-refresh every 30 seconds (throttled)
        let lastRefresh = 0;
        const refreshInterval = 30000;
        
        setInterval(() => {
            const now = Date.now();
            if (now - lastRefresh >= refreshInterval) {
                lastRefresh = now;
                debouncedLoad();
            }
        }, refreshInterval);
    </script>
</body>
</html>
"""

@business_dashboard_bp.route('/')
@login_required
def dashboard():
    """Main dashboard page"""
    return render_template_string(DASHBOARD_HTML)

@business_dashboard_bp.route('/api/data')
@login_required
def dashboard_data():
    """API endpoint for dashboard data - Connects ALL platforms"""
    try:
        # ============================================================
        # GET DATA FROM LEAD-DASHBOARD DATABASE
        # ============================================================
        
        # Get contacts from database
        db_contacts = Lead.query.filter(Lead.status != LeadStatus.NEW).count()
        db_new = Lead.query.filter_by(status=LeadStatus.NEW).count()
        db_contacted = Lead.query.filter_by(status=LeadStatus.CONTACTED).count()
        db_replied = Lead.query.filter_by(status=LeadStatus.REPLIED).count()
        db_closed = Lead.query.filter_by(status=LeadStatus.CLOSED).count()
        db_lost = Lead.query.filter_by(status=LeadStatus.LOST).count()
        
        # Get hot leads from database
        db_hot_leads = Lead.query.filter(
            Lead.temperature == LeadTemperature.HOT,
            Lead.status != LeadStatus.CLOSED
        ).order_by(Lead.lead_score.desc()).limit(10).all()
        
        # Get recent contact logs
        recent_logs = ContactLog.query.order_by(ContactLog.sent_at.desc()).limit(5).all()
        
        # ============================================================
        # GET DATA FROM TRACKING SYSTEM (website-generator)
        # ============================================================
        
        tracking_data = {}
        hot_leads_data = []
        revenue_stats = {'total_revenue': 0, 'by_month': {}}
        weekly_performance = {}
        funnel_data = {}
        rates = {}
        
        if TRACKING_AVAILABLE:
            try:
                # Get conversion stats
                stats = tracker.get_funnel_stats()
                funnel_data = stats.get('funnel', {})
                rates = stats.get('conversion_rates', {})
                
                # Get demo analytics
                demo_stats_all = get_all_stats()
                if demo_stats_all:
                    dashboard_obj = LeadScoringDashboard()
                    hot_leads = dashboard_obj.get_hot_leads(limit=10)
                    
                    # Match hot leads with database leads
                    for hot_lead in hot_leads:
                        # Try to find matching lead in database
                        db_lead = Lead.query.filter(
                            db.func.lower(Lead.name) == hot_lead['business_name'].lower()
                        ).first()
                        
                        hot_leads_data.append({
                            'name': hot_lead['business_name'],
                            'score': hot_lead['hotness_score'],
                            'views': hot_lead['views'],
                            'interactions': hot_lead['interactions'],
                            'id': db_lead.id if db_lead else None,
                            'phone': db_lead.phone if db_lead else None,
                            'city': db_lead.city if db_lead else None
                        })
                
                # Get revenue stats
                revenue_stats = payment_tracker.get_revenue_stats()
                
                # Get performance metrics
                monitor = PerformanceMonitor()
                weekly_performance = monitor.get_weekly_report()
                
            except Exception as e:
                print(f"Warning: Error loading tracking data: {e}")
        
        # ============================================================
        # COMBINE DATA FROM BOTH SYSTEMS
        # ============================================================
        
        # Use database data as primary, tracking data as supplement
        total_contacts = max(db_contacts, funnel_data.get('leads_contacted', 0))
        closed_deals = max(db_closed, funnel_data.get('closed', 0))
        
        # Build funnel from combined data
        funnel_labels = ['New', 'Contacted', 'Replied', 'Closed', 'Lost']
        funnel_values = [
            db_new,
            db_contacted,
            db_replied,
            db_closed,
            db_lost
        ]
        
        # Build activity from recent logs
        activity = []
        for log in recent_logs:
            lead = log.lead
            if lead:
                activity.append({
                    'text': f"Contacted {lead.name} via {log.channel.value}",
                    'time': log.sent_at.strftime('%Y-%m-%d %H:%M') if log.sent_at else 'Recently'
                })
        
        # Add tracking activity
        if funnel_data.get('closed', 0) > 0:
            activity.append({
                'text': f"Closed {funnel_data.get('closed', 0)} deals (tracked)",
                'time': 'This week'
            })
        
        # Build response
        response = {
            'stats': {
                'total_contacts': total_contacts,
                'closed_deals': closed_deals,
                'total_revenue': revenue_stats.get('total_revenue', 0),
                'hot_leads': len(hot_leads_data) if hot_leads_data else len(db_hot_leads)
            },
            'sources': {
                'contacts': f"Database: {db_contacts} | Tracking: {funnel_data.get('leads_contacted', 0)}",
                'deals': f"Database: {db_closed} | Tracking: {funnel_data.get('closed', 0)}",
                'revenue': 'Payment Tracker',
                'hot_leads': f"Demo Analytics: {len(hot_leads_data)} | Database: {len(db_hot_leads)}"
            },
            'funnel': {
                'labels': funnel_labels,
                'values': funnel_values
            },
            'revenue': {
                'labels': list(revenue_stats.get('by_month', {}).keys())[-6:],
                'values': list(revenue_stats.get('by_month', {}).values())[-6:]
            },
            'hot_leads': hot_leads_data if hot_leads_data else [
                {
                    'name': lead.name,
                    'score': lead.lead_score,
                    'views': 0,
                    'interactions': 0,
                    'id': lead.id,
                    'phone': lead.phone,
                    'city': lead.city
                }
                for lead in db_hot_leads[:5]
            ],
            'activity': activity[:5],
            'performance': [
                {
                    'label': 'Daily Contacts',
                    'value': f"{weekly_performance.get('outreach', {}).get('daily_avg_contacts', 0):.1f}/day",
                    'target': '10+/day',
                    'on_target': weekly_performance.get('outreach', {}).get('daily_avg_contacts', 0) >= 10
                },
                {
                    'label': 'Conversion Rate',
                    'value': f"{rates.get('overall_conversion', 0):.1f}%",
                    'target': '8-10%',
                    'on_target': rates.get('overall_conversion', 0) >= 8
                },
                {
                    'label': 'Daily Revenue',
                    'value': f"€{weekly_performance.get('revenue', {}).get('daily_avg', 0):.2f}/day",
                    'target': '€100+/day',
                    'on_target': weekly_performance.get('revenue', {}).get('daily_avg', 0) >= 100
                }
            ],
            'action_items': [
                {'icon': '🔥', 'text': f"Contact {len(hot_leads_data) if hot_leads_data else len(db_hot_leads)} hot lead(s)"},
                {'icon': '📧', 'text': f"Follow up with {db_replied} replied leads"},
                {'icon': '📞', 'text': f"Contact {db_new} new leads today (target: 10/day)"}
            ],
            'connections': {
                'database': True,
                'tracking_available': TRACKING_AVAILABLE
            }
        }

        return jsonify(response)
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'connections': {'database': False, 'tracking_available': False}}), 500
