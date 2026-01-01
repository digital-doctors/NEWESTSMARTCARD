// State
let cards = [];
let editingCardId = null;
let locationEnabled = false;
let currentLocation = null;
let locationWatchId = null;
let notificationPermission = false;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
    registerServiceWorker();
});

// Register Service Worker for PWA
async function registerServiceWorker() {
    if ('serviceWorker' in navigator) {
        try {
            const registration = await navigator.serviceWorker.register('/static/service-worker.js');
            console.log('Service Worker registered:', registration);
            
            // Request notification permission
            if ('Notification' in window && 'PushManager' in window) {
                const permission = await Notification.requestPermission();
                notificationPermission = permission === 'granted';
            }
        } catch (error) {
            console.error('Service Worker registration failed:', error);
        }
    }
}

async function initializeApp() {
    await loadCards();
    setupEventListeners();
    checkLocationPermission();
}

// Event Listeners
function setupEventListeners() {
    // Add card button
    document.getElementById('add-card-btn').addEventListener('click', () => openCardModal());
    
    // Logout button
    document.getElementById('logout-btn').addEventListener('click', handleLogout);
    
    // Modal close buttons
    document.querySelectorAll('.modal-close, .modal-cancel').forEach(btn => {
        btn.addEventListener('click', closeModals);
    });
    
    // Card form
    document.getElementById('card-form').addEventListener('submit', handleCardSubmit);
    document.getElementById('add-bonus-btn').addEventListener('click', addBonusField);
    
    // Location permission
    document.getElementById('location-allow').addEventListener('click', enableLocation);
    document.getElementById('location-deny').addEventListener('click', () => {
        closeModals();
    });
    
    // Popup close
    document.querySelector('.popup-close').addEventListener('click', closeRecommendationPopup);
    
    // Click outside modal
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) closeModals();
        });
    });
}

// Logout
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

// Load Cards
async function loadCards() {
    try {
        const response = await fetch('/api/cards');
        if (response.status === 401 || response.status === 302) {
            window.location.href = '/login';
            return;
        }
        const data = await response.json();
        cards = data.cards;
        locationEnabled = data.location_enabled;
        
        displayCards();
        
        // Show location modal if needed
        if (cards.length > 0 && !locationEnabled) {
            setTimeout(() => showLocationModal(), 500);
        }
    } catch (error) {
        console.error('Error loading cards:', error);
    }
}

// Display Cards
function displayCards() {
    const cardsStack = document.getElementById('cards-stack');
    const emptyState = document.getElementById('empty-state');
    
    if (cards.length === 0) {
        cardsStack.innerHTML = '';
        emptyState.style.display = 'flex';
        return;
    }
    
    emptyState.style.display = 'none';
    
    cardsStack.innerHTML = cards.map((card, index) => `
        <div class="credit-card ${card.color}" data-card-id="${card.id}">
            <div class="card-header">
                <div class="card-name">${card.name}</div>
                <div class="card-network">${card.network}</div>
            </div>
            
            <div class="card-body">
                <div class="card-rate">${card.base_rate}%</div>
                <div class="card-rate-label">Base Cashback</div>
                
                ${card.category_bonuses && card.category_bonuses.length > 0 ? `
                    <div class="card-bonuses">
                        ${card.category_bonuses.map(bonus => `
                            <span class="bonus-badge">${formatCategory(bonus.category)} ${bonus.rate}%</span>
                        `).join('')}
                    </div>
                ` : ''}
            </div>
            
            <div class="card-actions">
                <button class="card-action-btn" onclick="editCard('${card.id}'); event.stopPropagation();" title="Edit">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                    </svg>
                </button>
                <button class="card-action-btn" onclick="deleteCard('${card.id}'); event.stopPropagation();" title="Delete">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="3 6 5 6 21 6"/>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                    </svg>
                </button>
            </div>
        </div>
    `).join('');
}

function formatCategory(category) {
    return category.charAt(0).toUpperCase() + category.slice(1);
}

// Card Modal
function openCardModal(cardData = null) {
    const modal = document.getElementById('card-modal');
    const title = document.getElementById('modal-title');
    
    if (cardData) {
        title.textContent = 'Edit Card';
        editingCardId = cardData.id;
        populateForm(cardData);
    } else {
        title.textContent = 'Add Card';
        editingCardId = null;
        document.getElementById('card-form').reset();
        document.getElementById('category-bonuses-list').innerHTML = '';
    }
    
    modal.classList.add('active');
}

function populateForm(cardData) {
    document.getElementById('card-name').value = cardData.name;
    document.getElementById('card-network').value = cardData.network;
    document.getElementById('card-color').value = cardData.color;
    document.getElementById('base-rate').value = cardData.base_rate;
    
    const bonusList = document.getElementById('category-bonuses-list');
    bonusList.innerHTML = '';
    
    if (cardData.category_bonuses) {
        cardData.category_bonuses.forEach(bonus => {
            addBonusField(bonus.category, bonus.rate);
        });
    }
}

function addBonusField(category = '', rate = '') {
    const bonusList = document.getElementById('category-bonuses-list');
    const bonusItem = document.createElement('div');
    bonusItem.className = 'bonus-item';
    
    bonusItem.innerHTML = `
        <select class="bonus-category">
            <option value="">Select Category</option>
            <option value="grocery" ${category === 'grocery' ? 'selected' : ''}>Grocery</option>
            <option value="gas" ${category === 'gas' ? 'selected' : ''}>Gas</option>
            <option value="restaurant" ${category === 'restaurant' ? 'selected' : ''}>Restaurant</option>
            <option value="travel" ${category === 'travel' ? 'selected' : ''}>Travel</option>
            <option value="pharmacy" ${category === 'pharmacy' ? 'selected' : ''}>Pharmacy</option>
            <option value="retail" ${category === 'retail' ? 'selected' : ''}>Retail</option>
        </select>
        <input type="number" class="bonus-rate" placeholder="Rate %" step="0.01" value="${rate}">
        <button type="button" class="bonus-remove">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M18 6L6 18M6 6l12 12"/>
            </svg>
        </button>
    `;
    
    bonusItem.querySelector('.bonus-remove').addEventListener('click', () => {
        bonusItem.remove();
    });
    
    bonusList.appendChild(bonusItem);
}

async function handleCardSubmit(e) {
    e.preventDefault();
    
    const cardData = {
        name: document.getElementById('card-name').value,
        network: document.getElementById('card-network').value,
        color: document.getElementById('card-color').value,
        base_rate: parseFloat(document.getElementById('base-rate').value),
        category_bonuses: []
    };
    
    document.querySelectorAll('.bonus-item').forEach(item => {
        const category = item.querySelector('.bonus-category').value;
        const rate = item.querySelector('.bonus-rate').value;
        
        if (category && rate) {
            cardData.category_bonuses.push({
                category: category,
                rate: parseFloat(rate)
            });
        }
    });
    
    try {
        let response;
        if (editingCardId) {
            response = await fetch(`/api/cards/${editingCardId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(cardData)
            });
        } else {
            response = await fetch('/api/cards', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(cardData)
            });
        }
        
        if (response.ok) {
            closeModals();
            await loadCards();
            
            // Show location modal if first card
            if (cards.length === 1 && !locationEnabled) {
                setTimeout(() => showLocationModal(), 500);
            }
        }
    } catch (error) {
        console.error('Error saving card:', error);
        alert('Failed to save card. Please try again.');
    }
}

function editCard(cardId) {
    const card = cards.find(c => c.id === cardId);
    if (card) {
        openCardModal(card);
    }
}

async function deleteCard(cardId) {
    if (!confirm('Delete this card?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/cards/${cardId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            await loadCards();
        }
    } catch (error) {
        console.error('Error deleting card:', error);
        alert('Failed to delete card. Please try again.');
    }
}

function closeModals() {
    document.querySelectorAll('.modal').forEach(modal => {
        modal.classList.remove('active');
    });
    editingCardId = null;
}

// Location Services
function showLocationModal() {
    const modal = document.getElementById('location-modal');
    modal.classList.add('active');
}

async function enableLocation() {
    closeModals();
    
    if (!navigator.geolocation) {
        alert('Geolocation is not supported by your browser');
        return;
    }
    
    try {
        // Request permission
        const position = await new Promise((resolve, reject) => {
            navigator.geolocation.getCurrentPosition(resolve, reject);
        });
        
        // Save permission
        await fetch('/api/location/enable', {
            method: 'POST'
        });
        
        locationEnabled = true;
        
        // Start watching location
        startLocationTracking();
        
        // Check immediately
        checkLocationForRecommendation(position.coords.latitude, position.coords.longitude);
        
    } catch (error) {
        console.error('Location permission denied:', error);
    }
}

function checkLocationPermission() {
    if (locationEnabled && navigator.geolocation) {
        startLocationTracking();
    }
}

function startLocationTracking() {
    if (locationWatchId) {
        navigator.geolocation.clearWatch(locationWatchId);
    }
    
    
    locationWatchId = navigator.geolocation.watchPosition(
        (position) => {
            currentLocation = {
                latitude: position.coords.latitude,
                longitude: position.coords.longitude
            };
            checkLocationForRecommendation(position.coords.latitude, position.coords.longitude);
        },
        (error) => {
            console.error('Location tracking error:', error);
        },
        {
            enableHighAccuracy: true,
            timeout: 5000,
            maximumAge: 30000
        }
    );
}

let lastRecommendationTime = 0;
const RECOMMENDATION_COOLDOWN = 60000; // 1 minute

async function checkLocationForRecommendation(lat, lng) {
    if (cards.length === 0) return;
    
    
    const now = Date.now();
    if (now - lastRecommendationTime < RECOMMENDATION_COOLDOWN) {
        return;
    }
    
    try {
        const response = await fetch('/api/location/check', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ latitude: lat, longitude: lng })
        });
        
        const data = await response.json();
        
        if (data.success && data.recommendation) {
            lastRecommendationTime = now;
            showRecommendationPopup(data.recommendation);
        }
    } catch (error) {
        console.error('Error checking location:', error);
    }
}

function showRecommendationPopup(recommendation) {
    const popup = document.getElementById('recommendation-popup');
    const content = document.getElementById('recommendation-content');
    
    const merchant = recommendation.merchant;
    const allNearby = recommendation.all_nearby || [];
    const location = recommendation.location;
    
    // Format nearby merchants list
    const nearbyList = allNearby.slice(0, 5).map(m => 
        `${m.name} (${m.distance.toFixed(1)} mi)`
    ).join(', ');
    
    // GIFT CARD RECOMMENDATION (Priority)
    if (recommendation.type === 'gift_card') {
        const giftCard = recommendation.gift_card;
        
        content.innerHTML = `
            <div style="background: linear-gradient(135deg, #FF6B6B 0%, #FF8E53 100%); border-radius: 16px; padding: 24px; color: white; margin-bottom: 16px; box-shadow: 0 4px 20px rgba(255, 107, 107, 0.3);">
                <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px;">
                    <span style="font-size: 32px;">🎁</span>
                    <div>
                        <div style="font-size: 20px; font-weight: 600;">Use Your Gift Card!</div>
                        <div style="font-size: 14px; opacity: 0.9; margin-top: 4px;">${giftCard.merchant}</div>
                    </div>
                </div>
                <div style="font-size: 32px; font-weight: 700; margin: 16px 0; text-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);">$${parseFloat(giftCard.balance).toFixed(2)}</div>
                <div style="font-size: 13px; opacity: 0.9;">Available Balance</div>
            </div>
            
            <div style="background: var(--bg-primary); border-radius: 12px; padding: 16px; margin-bottom: 16px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <strong style="color: var(--text-primary);">Nearby Merchant</strong>
                    <span class="merchant-category">${merchant.category}</span>
                </div>
                <div style="font-size: 18px; font-weight: 600; color: var(--text-primary); margin-bottom: 4px;">
                    ${merchant.name}
                </div>
                <div style="font-size: 14px; color: var(--text-secondary);">
                    📍 ${merchant.distance.toFixed(2)} miles away
                </div>
            </div>
            
            <div style="padding: 12px 16px; background: #FFF3CD; border-radius: 8px; border-left: 4px solid #FFC107;">
                <div style="color: #856404; font-size: 14px; font-weight: 500;">
                    ⭐ Use your gift card first to save your credit card rewards!
                </div>
            </div>
            
            ${allNearby.length > 1 ? `
                <div style="margin-top: 12px; padding: 12px; background: var(--bg-primary); border-radius: 8px;">
                    <div style="font-size: 12px; color: var(--text-secondary); margin-bottom: 4px;">
                        ${allNearby.length - 1} other location${allNearby.length !== 2 ? 's' : ''} nearby
                    </div>
                    <div style="font-size: 13px; color: var(--text-primary);">
                        ${nearbyList.split(', ').slice(1).join(', ')}
                    </div>
                </div>
            ` : ''}
        `;
    }
    // CREDIT CARD RECOMMENDATION
    else if (recommendation.type === 'credit_card') {
        const card = recommendation.card;
        
        content.innerHTML = `
            <div style="background: var(--bg-primary); border-radius: 12px; padding: 16px; margin-bottom: 16px;">
                <div style="display: flex; align-items: center; gap: 8px; color: var(--text-secondary); font-size: 14px; margin-bottom: 12px;">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>
                        <circle cx="12" cy="10" r="3"/>
                    </svg>
                    <span>Your current location: ${location.lat.toFixed(4)}, ${location.lng.toFixed(4)}</span>
                </div>
                <p style="color: var(--text-secondary); font-size: 14px; line-height: 1.6;">
                    You are near <strong style="color: var(--text-primary);">${allNearby.length} bonus location${allNearby.length !== 1 ? 's' : ''}</strong>: ${nearbyList}${allNearby.length > 5 ? `, and ${allNearby.length - 5} more` : ''}
                </p>
            </div>
            
            <div class="recommendation-card">
                <div style="font-size: 14px; color: var(--text-secondary); margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 500;">
                    Recommended Card
                </div>
                <div class="recommendation-card-name">${card.name}</div>
                <div class="recommendation-rate">${recommendation.rate}% cashback</div>
                <div style="display: flex; align-items: center; gap: 8px; margin-top: 12px;">
                    <span style="color: var(--text-secondary); font-size: 14px;">Best for</span>
                    <span class="merchant-category">${merchant.category}</span>
                    <span style="color: var(--text-secondary); font-size: 14px;">at ${merchant.name}</span>
                </div>
                <p style="margin-top: 12px; color: var(--text-secondary); font-size: 13px;">
                    Closest bonus location: ${merchant.distance.toFixed(1)} miles away
                </p>
            </div>
        `;
    }
    
    popup.classList.add('show');
    
    // Auto-hide after 10 seconds
    setTimeout(() => {
        closeRecommendationPopup();
    }, 10000);
}

function closeRecommendationPopup() {
    const popup = document.getElementById('recommendation-popup');
    popup.classList.remove('show');
}

// Make functions global
window.editCard = editCard;
window.deleteCard = deleteCard;