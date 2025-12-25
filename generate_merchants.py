"""
OpenStreetMap Merchant Data Generator for SmartCard
This script fetches merchant locations from OpenStreetMap and generates JSON files
"""

import requests
import json
import time
from typing import List, Dict

# OpenStreetMap Overpass API endpoint
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Cities to generate data for
CITIES = {
    "chicago": {"lat": 41.8781, "lng": -87.6298, "radius": 5000},  # 5km radius
    "new_york": {"lat": 40.7128, "lng": -74.0060, "radius": 5000},
    "los_angeles": {"lat": 34.0522, "lng": -118.2437, "radius": 5000},
    "austin": {"lat": 30.2672, "lng": -97.7431, "radius": 5000},
    "san_francisco": {"lat": 37.7749, "lng": -122.4194, "radius": 5000},
}

# Full state/region coverage (WARNING: Very large queries!)
# Use for comprehensive coverage of entire states
STATES = {
    "illinois": {
        "type": "state",
        "bbox": {
            "south": 36.9701,   # Southern tip of Illinois
            "north": 42.5083,   # Northern border with Wisconsin
            "west": -91.5130,   # Western border with Iowa/Missouri
            "east": -87.0199    # Eastern border with Indiana (Lake Michigan)
        }
    }
}


def build_overpass_query(lat: float, lng: float, radius: int) -> str:
    """
    Build Overpass QL query to fetch merchants by category
    
    OSM Tags Used:
    - shop=supermarket → grocery
    - amenity=restaurant, cafe, fast_food → restaurant  
    - amenity=fuel → gas
    - amenity=pharmacy → pharmacy
    - shop=* (general retail) → retail
    """
    query = f"""
    [out:json][timeout:90];
    (
      // Grocery stores and supermarkets
      node["shop"="supermarket"](around:{radius},{lat},{lng});
      way["shop"="supermarket"](around:{radius},{lat},{lng});
      
      // Restaurants and cafes
      node["amenity"="restaurant"](around:{radius},{lat},{lng});
      way["amenity"="restaurant"](around:{radius},{lat},{lng});
      node["amenity"="cafe"](around:{radius},{lat},{lng});
      way["amenity"="cafe"](around:{radius},{lat},{lng});
      node["amenity"="fast_food"](around:{radius},{lat},{lng});
      way["amenity"="fast_food"](around:{radius},{lat},{lng});
      
      // Gas stations
      node["amenity"="fuel"](around:{radius},{lat},{lng});
      way["amenity"="fuel"](around:{radius},{lat},{lng});
      
      // Pharmacies
      node["amenity"="pharmacy"](around:{radius},{lat},{lng});
      way["amenity"="pharmacy"](around:{radius},{lat},{lng});
      
      // Retail stores
      node["shop"="convenience"](around:{radius},{lat},{lng});
      way["shop"="convenience"](around:{radius},{lat},{lng});
      node["shop"="clothes"](around:{radius},{lat},{lng});
      way["shop"="clothes"](around:{radius},{lat},{lng});
      node["shop"="department_store"](around:{radius},{lat},{lng});
      way["shop"="department_store"](around:{radius},{lat},{lng});
    );
    out center;
    """
    return query


def build_state_query(bbox: Dict) -> str:
    """
    Build Overpass QL query for an entire state/region
    This fetches ALL merchant types in the bounding box
    
    WARNING: This is a LARGE query and may take 5-10 minutes!
    """
    south, north = bbox['south'], bbox['north']
    west, east = bbox['west'], bbox['east']
    
    query = f"""
    [out:json][timeout:300][bbox:{south},{west},{north},{east}];
    (
      // ALL grocery/food stores
      node["shop"="supermarket"];
      way["shop"="supermarket"];
      node["shop"="convenience"];
      way["shop"="convenience"];
      node["shop"="grocery"];
      way["shop"="grocery"];
      
      // ALL restaurants and food service
      node["amenity"="restaurant"];
      way["amenity"="restaurant"];
      node["amenity"="cafe"];
      way["amenity"="cafe"];
      node["amenity"="fast_food"];
      way["amenity"="fast_food"];
      node["amenity"="bar"];
      way["amenity"="bar"];
      node["amenity"="pub"];
      way["amenity"="pub"];
      
      // ALL gas stations
      node["amenity"="fuel"];
      way["amenity"="fuel"];
      
      // ALL pharmacies
      node["amenity"="pharmacy"];
      way["amenity"="pharmacy"];
      node["shop"="chemist"];
      way["shop"="chemist"];
      
      // ALL retail stores
      node["shop"="mall"];
      way["shop"="mall"];
      node["shop"="department_store"];
      way["shop"="department_store"];
      node["shop"="clothes"];
      way["shop"="clothes"];
      node["shop"="shoes"];
      way["shop"="shoes"];
      node["shop"="electronics"];
      way["shop"="electronics"];
      node["shop"="furniture"];
      way["shop"="furniture"];
      node["shop"="hardware"];
      way["shop"="hardware"];
      node["shop"="jewelry"];
      way["shop"="jewelry"];
      node["shop"="sports"];
      way["shop"="sports"];
      node["shop"="toys"];
      way["shop"="toys"];
      node["shop"="books"];
      way["shop"="books"];
      node["shop"="gift"];
      way["shop"="gift"];
      node["shop"="florist"];
      way["shop"="florist"];
      node["shop"="pet"];
      way["shop"="pet"];
      node["shop"="cosmetics"];
      way["shop"="cosmetics"];
      node["shop"="beauty"];
      way["shop"="beauty"];
      node["shop"="hairdresser"];
      way["shop"="hairdresser"];
      
      // Wholesale/big box stores
      node["shop"="wholesale"];
      way["shop"="wholesale"];
      node["shop"="warehouse"];
      way["shop"="warehouse"];
    );
    out center;
    """
    return query


def categorize_merchant(tags: Dict) -> str:
    """Determine SmartCard category from OSM tags - EXPANDED CATEGORIES"""
    
    # Check shop types
    shop = tags.get("shop", "")
    amenity = tags.get("amenity", "")
    
    # Grocery - includes all food stores
    if shop in ["supermarket", "greengrocer", "marketplace", "convenience", "grocery"]:
        return "grocery"
    
    # Restaurant - includes all food service
    if amenity in ["restaurant", "cafe", "fast_food", "food_court", "pub", "bar", "biergarten"]:
        return "restaurant"
    
    # Gas
    if amenity == "fuel":
        return "gas"
    
    # Pharmacy
    if amenity == "pharmacy" or shop == "chemist":
        return "pharmacy"
    
    # Retail (everything else with a shop tag)
    if shop in [
        "mall", "department_store", "clothes", "shoes", "electronics", 
        "furniture", "hardware", "jewelry", "sports", "toys", "books", 
        "gift", "florist", "pet", "cosmetics", "beauty", "hairdresser",
        "wholesale", "warehouse", "general", "variety_store"
    ]:
        return "retail"
    
    # Default to retail if it has any shop tag
    if shop:
        return "retail"
    
    return "retail"  # Default


def fetch_merchants_from_state(bbox: Dict) -> List[Dict]:
    """Fetch ALL merchant data for an entire state using bounding box"""
    
    query = build_state_query(bbox)
    
    print(f"⚠️  WARNING: Querying ENTIRE STATE - This will take 5-10 minutes!")
    print(f"Bounding box: {bbox}")
    print(f"This may return 10,000+ merchants...")
    
    try:
        response = requests.post(
            OVERPASS_URL,
            data={"data": query},
            timeout=600  # 10 minute timeout for large queries
        )
        
        if response.status_code != 200:
            print(f"Error: API returned status {response.status_code}")
            return []
        
        data = response.json()
        elements = data.get("elements", [])
        
        print(f"Received {len(elements)} elements from OSM")
        
        merchants = []
        seen_names = set()  # Avoid duplicates
        
        for element in elements:
            tags = element.get("tags", {})
            name = tags.get("name")
            
            # Skip unnamed places
            if not name:
                continue
            
            # For states, allow duplicate names since they're in different locations
            # Just use unique ID instead
            unique_id = f"{name}_{element.get('id')}"
            if unique_id in seen_names:
                continue
            seen_names.add(unique_id)
            
            # Get coordinates (for ways, use center point)
            if element["type"] == "node":
                merchant_lat = element.get("lat")
                merchant_lng = element.get("lon")
            elif element["type"] == "way" and "center" in element:
                merchant_lat = element["center"].get("lat")
                merchant_lng = element["center"].get("lon")
            else:
                continue  # Skip if no coordinates
            
            # Determine category
            category = categorize_merchant(tags)
            
            merchant = {
                "name": name,
                "category": category,
                "lat": merchant_lat,
                "lon": merchant_lng,
                "osm_id": element.get("id"),
                "osm_type": element.get("type")
            }
            
            merchants.append(merchant)
        
        print(f"Processed {len(merchants)} unique merchants")
        return merchants
        
    except Exception as e:
        print(f"Error fetching from OSM: {e}")
        return []
def fetch_merchants_from_osm(lat: float, lng: float, radius: int) -> List[Dict]:
    """Fetch merchant data from OpenStreetMap Overpass API"""
    
    query = build_overpass_query(lat, lng, radius)
    
    print(f"Querying OSM for location ({lat}, {lng}) with radius {radius}m...")
    
    try:
        response = requests.post(
            OVERPASS_URL,
            data={"data": query},
            timeout=120
        )
        
        if response.status_code != 200:
            print(f"Error: API returned status {response.status_code}")
            return []
        
        data = response.json()
        elements = data.get("elements", [])
        
        print(f"Received {len(elements)} elements from OSM")
        
        merchants = []
        seen_names = set()  # Avoid duplicates
        
        for element in elements:
            tags = element.get("tags", {})
            name = tags.get("name")
            
            # Skip unnamed places
            if not name:
                continue
            
            # Skip duplicates
            if name in seen_names:
                continue
            seen_names.add(name)
            
            # Get coordinates (for ways, use center point)
            if element["type"] == "node":
                merchant_lat = element.get("lat")
                merchant_lng = element.get("lon")
            elif element["type"] == "way" and "center" in element:
                merchant_lat = element["center"].get("lat")
                merchant_lng = element["center"].get("lon")
            else:
                continue  # Skip if no coordinates
            
            # Determine category
            category = categorize_merchant(tags)
            
            merchant = {
                "name": name,
                "category": category,
                "lat": merchant_lat,
                "lon": merchant_lng,
                "osm_id": element.get("id"),
                "osm_type": element.get("type")
            }
            
            merchants.append(merchant)
        
        print(f"Processed {len(merchants)} unique merchants")
        return merchants
        
    except Exception as e:
        print(f"Error fetching from OSM: {e}")
        return []


def generate_state_data(state_name: str, state_info: Dict) -> List[Dict]:
    """Generate merchant data for an entire state"""
    
    print(f"\n{'='*60}")
    print(f"Generating data for {state_name.upper()} (ENTIRE STATE)")
    print(f"{'='*60}")
    
    merchants = fetch_merchants_from_state(state_info["bbox"])
    
    # Add state tag to each merchant
    for merchant in merchants:
        merchant["state"] = state_name
    
    return merchants
    
    query = build_overpass_query(lat, lng, radius)
    
    print(f"Querying OSM for location ({lat}, {lng}) with radius {radius}m...")
    
    try:
        response = requests.post(
            OVERPASS_URL,
            data={"data": query},
            timeout=120
        )
        
        if response.status_code != 200:
            print(f"Error: API returned status {response.status_code}")
            return []
        
        data = response.json()
        elements = data.get("elements", [])
        
        print(f"Received {len(elements)} elements from OSM")
        
        merchants = []
        seen_names = set()  # Avoid duplicates
        
        for element in elements:
            tags = element.get("tags", {})
            name = tags.get("name")
            
            # Skip unnamed places
            if not name:
                continue
            
            # Skip duplicates
            if name in seen_names:
                continue
            seen_names.add(name)
            
            # Get coordinates (for ways, use center point)
            if element["type"] == "node":
                merchant_lat = element.get("lat")
                merchant_lng = element.get("lon")
            elif element["type"] == "way" and "center" in element:
                merchant_lat = element["center"].get("lat")
                merchant_lng = element["center"].get("lon")
            else:
                continue  # Skip if no coordinates
            
            # Determine category
            category = categorize_merchant(tags)
            
            merchant = {
                "name": name,
                "category": category,
                "lat": merchant_lat,
                "lon": merchant_lng,
                "osm_id": element.get("id"),
                "osm_type": element.get("type")
            }
            
            merchants.append(merchant)
        
        print(f"Processed {len(merchants)} unique merchants")
        return merchants
        
    except Exception as e:
        print(f"Error fetching from OSM: {e}")
        return []


def generate_city_data(city_name: str, city_info: Dict) -> List[Dict]:
    """Generate merchant data for a specific city"""
    
    print(f"\n{'='*60}")
    print(f"Generating data for {city_name.upper()}")
    print(f"{'='*60}")
    
    merchants = fetch_merchants_from_osm(
        city_info["lat"],
        city_info["lng"],
        city_info["radius"]
    )
    
    # Add city tag to each merchant
    for merchant in merchants:
        merchant["city"] = city_name
    
    return merchants


def save_to_json(merchants: List[Dict], filename: str):
    """Save merchant data to JSON file"""
    
    with open(filename, "w") as f:
        json.dump(merchants, f, indent=2)
    
    print(f"\n✅ Saved {len(merchants)} merchants to {filename}")


def generate_all_cities():
    """Generate merchant data for all configured cities"""
    
    all_merchants = []
    
    for city_name, city_info in CITIES.items():
        merchants = generate_city_data(city_name, city_info)
        all_merchants.extend(merchants)
        
        # Save individual city file
        city_filename = f"data/merchants_{city_name}.json"
        save_to_json(merchants, city_filename)
        
        # Be nice to OSM servers - wait between requests
        print("Waiting 5 seconds before next city...")
        time.sleep(5)
    
    # Save combined file
    combined_filename = "data/all_locations.json"
    save_to_json(all_merchants, combined_filename)
    
    # Print statistics
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Total merchants across all cities: {len(all_merchants)}")
    
    # Category breakdown
    category_counts = {}
    for m in all_merchants:
        cat = m["category"]
        category_counts[cat] = category_counts.get(cat, 0) + 1
    
    print("\nBy category:")
    for cat, count in sorted(category_counts.items()):
        print(f"  {cat.capitalize()}: {count}")
    
    print("\nBy city:")
    city_counts = {}
    for m in all_merchants:
        city = m.get("city", m.get("state", "unknown"))
        city_counts[city] = city_counts.get(city, 0) + 1
    
    for city, count in sorted(city_counts.items()):
        print(f"  {city.capitalize()}: {count}")


def generate_all_states():
    """Generate merchant data for all configured states - LARGE OPERATION!"""
    
    all_merchants = []
    
    for state_name, state_info in STATES.items():
        merchants = generate_state_data(state_name, state_info)
        all_merchants.extend(merchants)
        
        # Save individual state file
        state_filename = f"data/merchants_{state_name}.json"
        save_to_json(merchants, state_filename)
        
        # Be nice to OSM servers - wait longer between state requests
        print("Waiting 30 seconds before next state (if any)...")
        time.sleep(30)
    
    # Save combined file
    combined_filename = "data/all_locations.json"
    save_to_json(all_merchants, combined_filename)
    
    # Print statistics
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Total merchants across all states: {len(all_merchants)}")
    
    # Category breakdown
    category_counts = {}
    for m in all_merchants:
        cat = m["category"]
        category_counts[cat] = category_counts.get(cat, 0) + 1
    
    print("\nBy category:")
    for cat, count in sorted(category_counts.items()):
        print(f"  {cat.capitalize()}: {count}")
    
    print("\nBy state:")
    state_counts = {}
    for m in all_merchants:
        state = m.get("state", "unknown")
        state_counts[state] = state_counts.get(state, 0) + 1
    
    for state, count in sorted(state_counts.items()):
        print(f"  {state.capitalize()}: {count}")


if __name__ == "__main__":
    import os
    import sys
    
    # Create data directory if it doesn't exist
    os.makedirs("data", exist_ok=True)
    
    print("SmartCard Merchant Data Generator")
    print("Using OpenStreetMap Overpass API")
    print("="*60)
    print("\nChoose data generation mode:")
    print("  1. Cities only (5-10 minutes, ~5,000 merchants)")
    print("  2. Illinois only (10-15 minutes, ~15,000+ merchants)")
    print("  3. Both cities + Illinois (15-20 minutes, ~20,000+ merchants)")
    print()
    
    mode = input("Enter choice (1/2/3): ").strip()
    
    if mode == "1":
        print("\n🏙️  Generating city data only...")
        generate_all_cities()
    elif mode == "2":
        print("\n🗺️  Generating Illinois state data only...")
        generate_all_states()
    elif mode == "3":
        print("\n🌎 Generating both cities and Illinois...")
        generate_all_cities()
        print("\n" + "="*60)
        print("Now generating Illinois state data...")
        print("="*60)
        generate_all_states()
    else:
        print("Invalid choice. Defaulting to cities only...")
        generate_all_cities()
    
    print("\n✨ All done! Your merchant data is ready to use.")
    print("You can now run your Flask app with the generated all_locations.json")