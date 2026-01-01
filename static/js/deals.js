// Deals Page JavaScript

let currentLocation = null;

document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    checkLocationStatus();
});

function setupEventListeners() {
    // Find deals button
    document.getElementById('find-deals-btn').addEventListener('click', findDeals);
    
    // Logout button
    document.getElementById('logout-btn-nav').addEventListener('click', handleLogout);
}

async function handleLogout() {
    if (confirm('Are you sure you want to log out?')) {
        try {
            await fetch('/api/auth/logout', {
                method: 'POST'
            });
            window.location.href = '/login';
        } catch (error) {
            console.error('Logout error:', error);
        }
    }
}

function checkLocationStatus() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (position) => {
                currentLocation = {
                    lat: position.coords.latitude,
                    lng: position.coords.longitude
                };
                updateLocationStatus(true);
            },
            (error) => {
                console.error('Location error:', error);
                updateLocationStatus(false);
            }
        );
    } else {
        updateLocationStatus(false);
    }
}

function updateLocationStatus(enabled) {
    const locationText = document.getElementById('location-text');
    const locationStatus = document.getElementById('location-status');
    
    if (enabled && currentLocation) {
        locationText.textContent = `Location enabled (${currentLocation.lat.toFixed(4)}, ${currentLocation.lng.toFixed(4)})`;
        locationStatus.style.background = 'rgba(76, 175, 80, 0.3)';
    } else {
        locationText.textContent = 'Enable location to see deals';
        locationStatus.style.background = 'rgba(255, 152, 0, 0.3)';
    }
}

async function findDeals() {
    if (!currentLocation) {
        alert('Please enable location services to find deals near you');
        return;
    }
    
    // Show loading
    document.getElementById('deals-empty').style.display = 'none';
    document.getElementById('deals-grid').style.display = 'none';
    document.getElementById('deals-loading').style.display = 'block';
    
    try {
        const response = await fetch('/api/deals/find', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                latitude: currentLocation.lat,
                longitude: currentLocation.lng
            })
        });
        
        const data = await response.json();
        
        if (data.success && data.stores) {
            displayDeals(data.stores);
        } else {
            showError(data.error || 'Could not find deals');
        }
    } catch (error) {
        console.error('Error finding deals:', error);
        showError('Failed to find deals. Please try again.');
    }
}

function displayDeals(stores) {
    document.getElementById('deals-loading').style.display = 'none';
    
    const dealsGrid = document.getElementById('deals-grid');
    dealsGrid.innerHTML = '';
    
    if (!stores || stores.length === 0) {
        document.getElementById('deals-empty').style.display = 'flex';
        return;
    }
    
    stores.forEach(store => {
        const storeCard = createStoreCard(store);
        dealsGrid.appendChild(storeCard);
    });
    
    dealsGrid.style.display = 'grid';
    
    // Smooth scroll to results
    dealsGrid.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function createStoreCard(store) {
    const card = document.createElement('div');
    card.className = 'deal-store-card';
    
    const dealsCount = store.deals ? store.deals.length : 0;
    
    card.innerHTML = `
        <div class="store-header">
            <h2 class="store-name">🏪 ${store.store}</h2>
            <p class="deals-count">${dealsCount} deal${dealsCount !== 1 ? 's' : ''} found</p>
        </div>
        
        ${store.error ? `
            <div class="deal-item" style="background: rgba(255, 107, 107, 0.2);">
                ⚠️ ${store.error}
            </div>
        ` : ''}
        
        ${store.deals && store.deals.length > 0 ? `
            <ul class="deals-list">
                ${store.deals.map((deal, index) => `
                    <li class="deal-item">
                        <strong>${index + 1}.</strong> ${formatDeal(deal)}
                    </li>
                `).join('')}
            </ul>
        ` : ''}
    `;
    
    return card;
}

function formatDeal(deal) {
    // Clean up the deal text and make it more readable
    let formatted = deal;
    
    // Remove asterisks and extra formatting
    formatted = formatted.replace(/\*\*/g, '');
    formatted = formatted.replace(/\*/g, '');
    
    // Remove leading numbers if present
    formatted = formatted.replace(/^\d+\.\s*/, '');
    
    // Highlight prices
    formatted = formatted.replace(/\$[\d,]+(\.\d{2})?/g, '<strong style="color: #FFD700;">$&</strong>');
    
    // Highlight percentages
    formatted = formatted.replace(/\d+%\s*(off|discount)/gi, '<strong style="color: #4CAF50;">$&</strong>');
    
    return formatted;
}

function showError(message) {
    document.getElementById('deals-loading').style.display = 'none';
    document.getElementById('deals-grid').style.display = 'none';
    
    const emptyState = document.getElementById('deals-empty');
    emptyState.innerHTML = `
        <div class="empty-icon">
            <svg width="80" height="80" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="8" x2="12" y2="12"/>
                <line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
        </div>
        <h2>Oops! Something went wrong</h2>
        <p>${message}</p>
        <button onclick="location.reload()" class="find-deals-btn" style="margin-top: 24px;">
            Try Again
        </button>
    `;
    emptyState.style.display = 'flex';
}