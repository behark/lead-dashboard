/**
 * Performance Optimizations
 * - Lazy loading
 * - Debouncing
 * - Caching
 * - Virtual scrolling for large lists
 */

class PerformanceOptimizer {
    constructor() {
        this.cache = new Map();
        this.init();
    }
    
    init() {
        // Lazy load images
        this.setupLazyLoading();
        
        // Debounce search inputs
        this.setupDebouncedSearch();
        
        // Cache API responses
        this.setupResponseCache();
        
        // Virtual scrolling for large lists
        this.setupVirtualScrolling();
        
        // Preload critical resources
        this.preloadCriticalResources();
    }
    
    setupLazyLoading() {
        // Use Intersection Observer for lazy loading
        if ('IntersectionObserver' in window) {
            const imageObserver = new IntersectionObserver((entries, observer) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const img = entry.target;
                        if (img.dataset.src) {
                            img.src = img.dataset.src;
                            img.removeAttribute('data-src');
                            observer.unobserve(img);
                        }
                    }
                });
            }, {
                rootMargin: '50px' // Load 50px before entering viewport
            });
            
            // Observe all images with data-src
            document.querySelectorAll('img[data-src]').forEach(img => {
                imageObserver.observe(img);
            });
            
            // Also observe lead cards for lazy rendering
            const cardObserver = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        entry.target.classList.add('visible');
                    }
                });
            }, {
                rootMargin: '100px'
            });
            
            document.querySelectorAll('.lead-card').forEach(card => {
                cardObserver.observe(card);
            });
        }
    }
    
    setupDebouncedSearch() {
        const searchInputs = document.querySelectorAll('input[type="search"], input[name="search"]');
        
        searchInputs.forEach(input => {
            let timeout;
            input.addEventListener('input', (e) => {
                clearTimeout(timeout);
                timeout = setTimeout(() => {
                    // Trigger search after 300ms of no typing
                    this.performSearch(e.target.value);
                }, 300);
            });
        });
    }
    
    performSearch(query) {
        // Check cache first
        const cacheKey = `search:${query}`;
        if (this.cache.has(cacheKey)) {
            console.log('Using cached search results');
            return this.cache.get(cacheKey);
        }
        
        // Otherwise, let the form submit naturally
        // Results will be cached when they arrive
    }
    
    setupResponseCache() {
        // Intercept fetch requests and cache responses
        const originalFetch = window.fetch;
        const cache = this.cache;
        
        window.fetch = async function(...args) {
            const url = args[0];
            
            // Only cache GET requests
            if (!args[1] || args[1].method === 'GET') {
                const cacheKey = `fetch:${url}`;
                
                // Check cache
                if (cache.has(cacheKey)) {
                    const cached = cache.get(cacheKey);
                    const age = Date.now() - cached.timestamp;
                    
                    // Use cache if less than 5 minutes old
                    if (age < 5 * 60 * 1000) {
                        console.log('Using cached response for:', url);
                        return Promise.resolve(new Response(JSON.stringify(cached.data), {
                            status: 200,
                            headers: { 'Content-Type': 'application/json' }
                        }));
                    }
                }
                
                // Fetch and cache
                const response = await originalFetch(...args);
                const clone = response.clone();
                
                try {
                    const data = await clone.json();
                    cache.set(cacheKey, {
                        data: data,
                        timestamp: Date.now()
                    });
                } catch (e) {
                    // Not JSON, skip caching
                }
                
                return response;
            }
            
            return originalFetch(...args);
        };
    }
    
    setupVirtualScrolling() {
        // For very large lists, only render visible items
        const container = document.querySelector('.lead-cards, .lead-table tbody');
        if (!container) return;
        
        const items = Array.from(container.children);
        if (items.length < 50) return; // Only for large lists
        
        const itemHeight = items[0]?.offsetHeight || 100;
        const viewportHeight = window.innerHeight;
        const visibleCount = Math.ceil(viewportHeight / itemHeight) + 2; // +2 for buffer
        
        let scrollTimeout;
        window.addEventListener('scroll', () => {
            clearTimeout(scrollTimeout);
            scrollTimeout = setTimeout(() => {
                this.updateVisibleItems(container, items, itemHeight, visibleCount);
            }, 50);
        }, { passive: true });
        
        // Initial render
        this.updateVisibleItems(container, items, itemHeight, visibleCount);
    }
    
    updateVisibleItems(container, items, itemHeight, visibleCount) {
        const scrollTop = window.pageYOffset;
        const startIndex = Math.floor(scrollTop / itemHeight);
        const endIndex = startIndex + visibleCount;
        
        items.forEach((item, index) => {
            if (index >= startIndex && index <= endIndex) {
                item.style.display = '';
            } else {
                item.style.display = 'none';
            }
        });
    }
    
    preloadCriticalResources() {
        // Preload fonts
        const fonts = [
            'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css'
        ];
        
        fonts.forEach(font => {
            const link = document.createElement('link');
            link.rel = 'preload';
            link.as = 'style';
            link.href = font;
            document.head.appendChild(link);
        });
        
        // Prefetch next page
        const nextPageLink = document.querySelector('.pagination .page-item:not(.active) + .page-item a');
        if (nextPageLink) {
            const link = document.createElement('link');
            link.rel = 'prefetch';
            link.href = nextPageLink.href;
            document.head.appendChild(link);
        }
    }
    
    // Service Worker for offline support
    registerServiceWorker() {
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/static/sw.js')
                .then(registration => {
                    console.log('Service Worker registered:', registration);
                })
                .catch(error => {
                    console.log('Service Worker registration failed:', error);
                });
        }
    }
    
    // Clear cache manually
    clearCache() {
        this.cache.clear();
        console.log('Cache cleared');
    }
    
    // Get cache stats
    getCacheStats() {
        return {
            size: this.cache.size,
            entries: Array.from(this.cache.keys())
        };
    }
}

// Initialize
const perfOptimizer = new PerformanceOptimizer();

// Export for global access
window.perfOptimizer = perfOptimizer;

// Add cache clear button to UI (for debugging)
document.addEventListener('DOMContentLoaded', () => {
    // Add to developer console
    console.log('Performance optimizer loaded. Use window.perfOptimizer.clearCache() to clear cache.');
    console.log('Cache stats:', perfOptimizer.getCacheStats());
});

// Monitor performance
if ('PerformanceObserver' in window) {
    const observer = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
            // Log slow operations
            if (entry.duration > 100) {
                console.warn('Slow operation detected:', entry.name, entry.duration + 'ms');
            }
        }
    });
    
    observer.observe({ entryTypes: ['measure', 'navigation'] });
}

// Add CSS for lazy loading animation
const perfStyle = document.createElement('style');
perfStyle.textContent = `
    .lead-card {
        opacity: 0;
        transform: translateY(20px);
        transition: opacity 0.3s ease, transform 0.3s ease;
    }
    
    .lead-card.visible {
        opacity: 1;
        transform: translateY(0);
    }
    
    img[data-src] {
        background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
        background-size: 200% 100%;
        animation: loading 1.5s infinite;
    }
    
    @keyframes loading {
        0% { background-position: 200% 0; }
        100% { background-position: -200% 0; }
    }
`;
document.head.appendChild(perfStyle);
