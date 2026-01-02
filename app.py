from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from functools import wraps
import json
import os
from datetime import datetime
import uuid
import math
import hashlib
import google.generativeai as genai
from google.generativeai.types import GenerationConfig
import time
from collections import defaultdict

app = Flask(__name__)
app.secret_key = 'smartcard-secret-key-change-in-production'
app.config['PERMANENT_SESSION_LIFETIME'] = 60 * 60 * 24 * 30  # 30 days
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'


GEMINI_API_KEY = "AIzaSyDQ6TEXoUqX963Mop7f71heOG9a---lwPM"
gemini_client = genai.configure(api_key=GEMINI_API_KEY)


USERS_FILE = os.path.join("data", "users.json")
MERCHANT_FILE = os.path.join("data", "all_locations.json")
DEALS_CACHE_FILE = os.path.join("data", "deals_cache.json")

class RateLimiter:
    def __init__(self):
        self.requests = defaultdict(list)
        
    def check_rate_limit(self, identifier, limit=10, window=60):
        """Check if the request is within rate limits"""
        current_time = time.time()
        
        # Clean old requests outside the window
        self.requests[identifier] = [
            req_time for req_time in self.requests[identifier]
            if current_time - req_time < window
        ]
        
        # Check if under limit
        if len(self.requests[identifier]) >= limit:
            return False, {
                'remaining': 0,
                'limit': limit,
                'reset_in': window - int(current_time - self.requests[identifier][0]) if self.requests[identifier] else window
            }
        
        # Add current request
        self.requests[identifier].append(current_time)
        
        return True, {
            'remaining': limit - len(self.requests[identifier]),
            'limit': limit,
            'reset_in': window
        }

rate_limiter = RateLimiter()

def rate_limit(limit=10, window=60):
    """Decorator to apply rate limiting to routes"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Use user email if logged in, otherwise IP address
            if 'user_email' in session:
                identifier = session['user_email']
            else:
                identifier = request.remote_addr
            
            allowed, rate_info = rate_limiter.check_rate_limit(identifier, limit, window)
            
            if not allowed:
                return jsonify({
                    'success': False,
                    'error': 'Rate limit exceeded',
                    'rate_limit': rate_info
                }), 429
            
            # Add rate limit info to response headers
            response = f(*args, **kwargs)
            if isinstance(response, tuple):
                response, status_code = response
                if hasattr(response, 'headers'):
                    response.headers['X-RateLimit-Limit'] = str(limit)
                    response.headers['X-RateLimit-Remaining'] = str(rate_info['remaining'])
                    response.headers['X-RateLimit-Reset'] = str(rate_info['reset_in'])
                return response, status_code
            else:
                if hasattr(response, 'headers'):
                    response.headers['X-RateLimit-Limit'] = str(limit)
                    response.headers['X-RateLimit-Remaining'] = str(rate_info['remaining'])
                    response.headers['X-RateLimit-Reset'] = str(rate_info['reset_in'])
                return response
            
        return decorated_function
    return decorator

# ==============================
# USER DATA MANAGEMENT
# ==============================

def load_users():
    """Load users from JSON file"""
    if not os.path.exists(USERS_FILE):
        return {"users": []}
    with open(USERS_FILE, 'r') as f:
        return json.load(f)

def save_users(users_data):
    """Save users to JSON file"""
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    with open(USERS_FILE, 'w') as f:
        json.dump(users_data, f, indent=2)

def hash_password(password):
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def find_user_by_email(email):
    """Find user by email"""
    users_data = load_users()
    for user in users_data['users']:
        if user['email'] == email:
            return user
    return None

def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

# ==============================
# DEALS CACHE MANAGEMENT
# ==============================

def load_deals_cache():
    """Load deals cache from JSON file"""
    if not os.path.exists(DEALS_CACHE_FILE):
        return {}
    try:
        with open(DEALS_CACHE_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_deals_cache(cache_data):
    """Save deals cache to JSON file"""
    os.makedirs(os.path.dirname(DEALS_CACHE_FILE), exist_ok=True)
    with open(DEALS_CACHE_FILE, 'w') as f:
        json.dump(cache_data, f, indent=2)

def get_user_deals(user_email):
    """Get cached deals for a specific user"""
    cache = load_deals_cache()
    user_cache = cache.get(user_email, {})
    
    # Check if cache is less than 24 hours old
    if user_cache.get('timestamp'):
        cache_time = datetime.fromisoformat(user_cache['timestamp'])
        age_hours = (datetime.now() - cache_time).total_seconds() / 3600
        if age_hours < 24:
            return user_cache.get('deals', [])
    
    return None

def set_user_deals(user_email, deals):
    """Cache deals for a specific user"""
    cache = load_deals_cache()
    cache[user_email] = {
        'deals': deals,
        'timestamp': datetime.now().isoformat()
    }
    save_deals_cache(cache)

# ==============================
# GIFT CARD DATA MANAGEMENT
# ==============================

def get_user_gift_cards(user_email):
    """Get gift cards for a specific user"""
    user = find_user_by_email(user_email)
    if user:
        return user.get('gift_cards', [])
    return []

def update_user_gift_cards(user_email, gift_cards):
    """Update gift cards for a specific user"""
    users_data = load_users()
    for user in users_data['users']:
        if user['email'] == user_email:
            user['gift_cards'] = gift_cards
            save_users(users_data)
            return True
    return False

def find_matching_gift_card(user_email, merchant_name, category=None):
    """Find a gift card that matches the merchant or category"""
    gift_cards = get_user_gift_cards(user_email)
    
    for card in gift_cards:
        if card['merchant'].lower() in merchant_name.lower() or merchant_name.lower() in card['merchant'].lower():
            if float(card['balance']) > 0:
                return card
        
        if category and card.get('category') and card['category'].lower() == category.lower():
            if float(card['balance']) > 0:
                return card
    
    return None

# ==============================
# LOAD MERCHANT DATA FROM JSON
# ==============================

def load_merchants():
    if not os.path.exists(MERCHANT_FILE):
        raise FileNotFoundError("Merchant data file not found")

    with open(MERCHANT_FILE, "r") as f:
        raw = json.load(f)

    merchants = []
    for m in raw:
        if m.get("category") not in {
            "grocery", "restaurant", "gas", "pharmacy", "retail"
        }:
            continue

        merchants.append({
            "name": m["name"],
            "category": m["category"],
            "lat": float(m["lat"]),
            "lng": float(m["lon"])
        })

    return merchants

MERCHANT_LOCATIONS = load_merchants()
print(f"Loaded {len(MERCHANT_LOCATIONS)} SmartCard merchants")

# ==============================
# UTILS
# ==============================

def calculate_distance(lat1, lng1, lat2, lng2):
    """Calculate distance between two coordinates in miles using Haversine formula"""
    R = 3959  # Earth's radius in miles

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lng = math.radians(lng2 - lng1)

    a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))

    return R * c

def get_user_id():
    """Get current user's email from session"""
    return session.get('user_email')

def get_user_cards(user_email):
    """Get cards for a specific user"""
    user = find_user_by_email(user_email)
    if user:
        return user.get('cards', [])
    return []

def update_user_cards(user_email, cards):
    """Update cards for a specific user"""
    users_data = load_users()
    for user in users_data['users']:
        if user['email'] == user_email:
            user['cards'] = cards
            save_users(users_data)
            return True
    return False

def get_user_location_enabled(user_email):
    """Check if location is enabled for user"""
    user = find_user_by_email(user_email)
    if user:
        return user.get('location_enabled', False)
    return False

def set_user_location_enabled(user_email, enabled):
    """Set location enabled status for user"""
    users_data = load_users()
    for user in users_data['users']:
        if user['email'] == user_email:
            user['location_enabled'] = enabled
            save_users(users_data)
            return True
    return False

def find_best_card_for_location(user_email, lat, lng):
    """Find the best card based on nearby merchants - PRIORITIZES GIFT CARDS"""
    cards = get_user_cards(user_email)
    
    nearby_merchants = []
    for merchant in MERCHANT_LOCATIONS:
        distance = calculate_distance(lat, lng, merchant['lat'], merchant['lng'])
        if distance <= 2.0:
            nearby_merchants.append({
                **merchant,
                'distance': distance
            })

    if not nearby_merchants:
        return None

    nearby_merchants.sort(key=lambda x: x['distance'])
    best_merchant = nearby_merchants[0]

    gift_card = find_matching_gift_card(user_email, best_merchant['name'], best_merchant['category'])
    
    if gift_card:
        return {
            'type': 'gift_card',
            'gift_card': gift_card,
            'merchant': best_merchant,
            'all_nearby': nearby_merchants,
            'location': {'lat': lat, 'lng': lng},
            'message': f'Use your {gift_card["merchant"]} gift card!'
        }

    if not cards:
        return None

    best_card = None
    best_value = 0

    for card in cards:
        value = 0
        for bonus in card.get('category_bonuses', []):
            if bonus['category'].lower() == best_merchant['category'].lower():
                value = float(bonus['rate'])
                break

        if value == 0:
            value = float(card.get('base_rate', 0))

        if value > best_value:
            best_value = value
            best_card = card

    return {
        'type': 'credit_card',
        'card': best_card,
        'merchant': best_merchant,
        'rate': best_value,
        'all_nearby': nearby_merchants,
        'location': {'lat': lat, 'lng': lng}
    }

# ==============================
# DEALS FUNCTIONALITY
# ==============================

def find_popular_stores_nearby(lat, lng, radius_miles=5, limit=3):
    """Find popular stores within radius, prioritizing well-known chains"""
    
    # Popular store chains to prioritize
    popular_chains = [
        'walmart', 'target', 'costco', 'kroger', 'safeway', 'whole foods',
        'cvs', 'walgreens', 'best buy', 'home depot', "lowe's", 'macy',
        'starbucks', 'mcdonalds', 'chipotle', 'panera', 'olive garden'
    ]
    
    nearby_stores = []
    for merchant in MERCHANT_LOCATIONS:
        distance = calculate_distance(lat, lng, merchant['lat'], merchant['lng'])
        if distance <= radius_miles:
            # Check if it's a popular chain
            is_popular = any(chain in merchant['name'].lower() for chain in popular_chains)
            
            nearby_stores.append({
                **merchant,
                'distance': distance,
                'is_popular': is_popular
            })
    
    # Sort by popularity first, then by distance
    nearby_stores.sort(key=lambda x: (not x['is_popular'], x['distance']))
    
    # Remove duplicates (same name)
    seen_names = set()
    unique_stores = []
    for store in nearby_stores:
        if store['name'] not in seen_names:
            seen_names.add(store['name'])
            unique_stores.append(store)
    
    return unique_stores[:limit]

def fetch_deals_for_store(store_name, category):
    """Use Gemini API to fetch 5 best deals for a specific store"""
    try:
        prompt = f"""Find the 5 BEST current promotional deals or discounts available at {store_name}. 
Focus on the most valuable, eye-catching deals that customers can use today. Include:
- Biggest percentage discounts
- Best dollar amount savings
- Most attractive BOGO offers
- Top category promotions
- Exact products on sale if possible

Format each deal as a short, catchy phrase (max 50 characters). Return ONLY a JSON array of 5 deals, like:
["Deal 1", "Deal 2", "Deal 3", "Deal 4", "Deal 5"]

Do not include any other text, just the JSON array."""

        # Create the model
        model = genai.GenerativeModel('gemini-pro')
        
        # Generate content
        response = model.generate_content(prompt)
        
        # Parse the response
        response_text = response.text.strip()
        
        # Try to extract JSON array
        if response_text.startswith('[') and response_text.endswith(']'):
            deals = json.loads(response_text)
            return deals[:5]  # Ensure max 5 deals
        else:
            # Fallback: try to find JSON in response
            import re
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if json_match:
                deals = json.loads(json_match.group(0))
                return deals[:5]
        
        # Fallback deals if parsing fails
        return [
            f"Special offers at {store_name}",
            f"Weekly deals on {category} items",
            "Check in-store for current promotions"
        ]
        
    except Exception as e:
        print(f"Error fetching deals for {store_name}: {e}")
        return [
            f"Current promotions at {store_name}",
            f"Deals on {category} items"
        ]



# ==============================
# AUTHENTICATION ROUTES
# ==============================

@app.route('/login')
def login_page():
    if 'user_email' in session:
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/register')
def register_page():
    if 'user_email' in session:
        return redirect(url_for('index'))
    return render_template('register.html')

@app.route("/profile")
@login_required
def profile():
    return render_template("profile.html")

@app.route('/api/auth/register', methods=['POST'])
@rate_limit(limit=5, window=60)  # More strict for registration
def register():
    data = request.json
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    
    if not name or not email or not password:
        return jsonify({'success': False, 'error': 'All fields are required'}), 400
    
    if find_user_by_email(email):
        return jsonify({'success': False, 'error': 'Email already registered'}), 400
    
    users_data = load_users()
    new_user = {
        'id': str(uuid.uuid4()),
        'name': name,
        'email': email,
        'password': hash_password(password),
        'cards': [],
        'gift_cards': [],
        'location_enabled': False,
        'created_at': datetime.now().isoformat()
    }
    
    users_data['users'].append(new_user)
    save_users(users_data)
    
    return jsonify({'success': True, 'message': 'Account created successfully'})

@app.route('/api/auth/login', methods=['POST'])
@rate_limit(limit=5, window=60)  # More strict for login attempts
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({'success': False, 'error': 'Email and password are required'}), 400
    
    user = find_user_by_email(email)
    
    if not user:
        return jsonify({'success': False, 'error': 'Invalid email or password'}), 401
    
    hashed_password = hash_password(password)
    
    if user['password'] != hashed_password:
        return jsonify({'success': False, 'error': 'Invalid email or password'}), 401
    
    session.permanent = True
    session['user_email'] = email
    
    return jsonify({'success': True, 'message': 'Login successful'})

@app.route('/api/auth/logout', methods=['POST'])
@login_required
@rate_limit()
def logout():
    session.pop('user_email', None)
    return jsonify({'success': True, 'message': 'Logged out successfully'})

# ==============================
# APP ROUTES
# ==============================

@app.route('/')
@login_required
def index():
    user_email = get_user_id()
    user = find_user_by_email(user_email)
    user_name = user.get('name', 'Friend') if user else 'Friend'
    first_name = user_name.split(' ')[0]
    return render_template('index.html', user_name=first_name)

@app.route('/service-worker.js')
def service_worker():
    return app.send_static_file('service-worker.js')

@app.route('/api/cards', methods=['GET'])
@login_required
@rate_limit()
def get_cards():
    user_email = get_user_id()
    cards = get_user_cards(user_email)
    location_enabled = get_user_location_enabled(user_email)
    return jsonify({'cards': cards, 'location_enabled': location_enabled})

@app.route('/api/user/info', methods=['GET'])
@login_required
@rate_limit()
def get_user_info():
    user_email = get_user_id()
    user = find_user_by_email(user_email)
    if user:
        return jsonify({
            'success': True,
            'name': user.get('name', 'Friend'),
            'email': user.get('email')
        })
    return jsonify({'success': False, 'error': 'User not found'}), 404

@app.route('/api/cards', methods=['POST'])
@login_required
@rate_limit()
def add_card():
    user_email = get_user_id()
    card_data = request.json

    card_data['id'] = str(uuid.uuid4())
    card_data['added_date'] = datetime.now().isoformat()

    cards = get_user_cards(user_email)
    cards.append(card_data)
    update_user_cards(user_email, cards)
    
    return jsonify({'success': True, 'card': card_data})

@app.route('/api/cards/<card_id>', methods=['DELETE'])
@login_required
@rate_limit()
def delete_card(card_id):
    user_email = get_user_id()
    cards = get_user_cards(user_email)

    updated_cards = [c for c in cards if c['id'] != card_id]
    update_user_cards(user_email, updated_cards)
    
    return jsonify({'success': True})

@app.route('/api/cards/<card_id>', methods=['PUT'])
@login_required
@rate_limit()
def update_card(card_id):
    user_email = get_user_id()
    cards = get_user_cards(user_email)
    card_data = request.json

    for i, card in enumerate(cards):
        if card['id'] == card_id:
            card_data['id'] = card_id
            card_data['added_date'] = card.get('added_date', datetime.now().isoformat())
            cards[i] = card_data
            update_user_cards(user_email, cards)
            return jsonify({'success': True, 'card': card_data})

    return jsonify({'success': False, 'error': 'Card not found'}), 404

@app.route('/api/location/enable', methods=['POST'])
@login_required
@rate_limit()
def enable_location():
    user_email = get_user_id()
    set_user_location_enabled(user_email, True)
    return jsonify({'success': True})

@app.route('/api/location/check', methods=['POST'])
@login_required
@rate_limit()
def check_location():
    user_email = get_user_id()
    data = request.json
    lat = data.get('latitude')
    lng = data.get('longitude')

    if not lat or not lng:
        return jsonify({'success': False, 'error': 'Invalid location'}), 400

    result = find_best_card_for_location(user_email, lat, lng)
    return jsonify({'success': True, 'recommendation': result})

# ==============================
# GIFT CARD ROUTES
# ==============================

@app.route("/gift-cards")
@login_required
def gift_cards():
    return render_template("gift_card.html")

@app.route("/deals")
@login_required
def deals():
    return render_template("deals.html")

@app.route('/api/gift-cards', methods=['GET'])
@login_required
@rate_limit()
def get_gift_cards():
    user_email = get_user_id()
    gift_cards = get_user_gift_cards(user_email)
    return jsonify({'gift_cards': gift_cards})

@app.route('/api/gift-cards', methods=['POST'])
@login_required
@rate_limit()
def add_gift_card():
    user_email = get_user_id()
    gift_card_data = request.json

    gift_card_data['id'] = str(uuid.uuid4())
    gift_card_data['added_date'] = datetime.now().isoformat()

    gift_cards = get_user_gift_cards(user_email)
    gift_cards.append(gift_card_data)
    update_user_gift_cards(user_email, gift_cards)
    
    return jsonify({'success': True, 'gift_card': gift_card_data})

@app.route('/api/gift-cards/<card_id>', methods=['DELETE'])
@login_required
@rate_limit()
def delete_gift_card(card_id):
    user_email = get_user_id()
    gift_cards = get_user_gift_cards(user_email)

    updated_gift_cards = [c for c in gift_cards if c['id'] != card_id]
    update_user_gift_cards(user_email, updated_gift_cards)
    
    return jsonify({'success': True})

@app.route('/api/gift-cards/<card_id>', methods=['PUT'])
@login_required
@rate_limit()
def update_gift_card(card_id):
    user_email = get_user_id()
    gift_cards = get_user_gift_cards(user_email)
    gift_card_data = request.json

    for i, card in enumerate(gift_cards):
        if card['id'] == card_id:
            gift_card_data['id'] = card_id
            gift_card_data['added_date'] = card.get('added_date', datetime.now().isoformat())
            gift_cards[i] = gift_card_data
            update_user_gift_cards(user_email, gift_cards)
            return jsonify({'success': True, 'gift_card': gift_card_data})

    return jsonify({'success': False, 'error': 'Gift card not found'}), 404

# ==============================
# DEALS API ROUTES
# ==============================

@app.route('/api/deals/fetch', methods=['POST'])
@login_required
@rate_limit(limit=5, window=60)  # More strict for deals fetching (costs money)
def fetch_deals():
    """Fetch deals based on user location"""
    user_email = get_user_id()
    data = request.json
    lat = data.get('latitude')
    lng = data.get('longitude')
    
    if not lat or not lng:
        return jsonify({'success': False, 'error': 'Location required'}), 400
    
    # Check for force refresh parameter
    force_refresh = request.args.get('refresh', 'false').lower() == 'true'
    
    # Check cache first (unless force refresh)
    if not force_refresh:
        cached_deals = get_user_deals(user_email)
        if cached_deals:
            return jsonify({
                'success': True, 
                'deals': cached_deals, 
                'from_cache': True,
                'timestamp': datetime.now().isoformat()
            })
    
    # Find popular stores nearby
    stores = find_popular_stores_nearby(lat, lng, radius_miles=5, limit=3)
    
    if not stores:
        return jsonify({'success': True, 'deals': [], 'message': 'No stores found nearby'})
    
    # Fetch deals for each store
    all_deals = []
    for store in stores:
        deals_list = fetch_deals_for_store(store['name'], store['category'])
        
        for deal_text in deals_list:
            all_deals.append({
                'id': str(uuid.uuid4()),
                'merchant': store['name'],
                'category': store['category'],
                'distance': round(store['distance'], 1),
                'deal_text': deal_text,
                'timestamp': datetime.now().isoformat()
            })
    
    # Cache the deals
    set_user_deals(user_email, all_deals)
    
    return jsonify({
        'success': True, 
        'deals': all_deals, 
        'from_cache': False,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/deals/cached', methods=['GET'])
@login_required
@rate_limit()
def get_cached_deals():
    """Get cached deals for user"""
    user_email = get_user_id()
    cached_deals = get_user_deals(user_email)
    
    if cached_deals:
        user_cache = load_deals_cache().get(user_email, {})
        return jsonify({
            'success': True, 
            'deals': cached_deals,
            'timestamp': user_cache.get('timestamp')
        })
    
    return jsonify({'success': True, 'deals': []})

# ==============================
# RATE LIMIT STATUS ENDPOINT
# ==============================

@app.route('/api/rate-limit/status', methods=['GET'])
@login_required
def get_rate_limit_status():
    """Get current rate limit status for user"""
    if 'user_email' in session:
        identifier = session['user_email']
    else:
        identifier = request.remote_addr
    
    current_time = time.time()
    
    # Clean old requests
    rate_limiter.requests[identifier] = [
        req_time for req_time in rate_limiter.requests[identifier]
        if current_time - req_time < 60
    ]
    
    remaining = 20 - len(rate_limiter.requests[identifier])
    
    return jsonify({
        'success': True,
        'rate_limit': {
            'remaining': max(0, remaining),
            'limit': 20,
            'window': 60,
            'reset_in': 60 - int(current_time - rate_limiter.requests[identifier][0]) if rate_limiter.requests[identifier] else 60
        }
    })

# ==============================
# RUN
# ==============================

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)
