import json

CATEGORY_MAP = {
    "supermarket": "grocery",
    "convenience": "grocery",
    "restaurant": "restaurant",
    "fast_food": "restaurant",
    "cafe": "restaurant",
    "pharmacy": "pharmacy",
    "fuel": "gas",
    "clothes": "retail",
    "electronics": "retail"
}

with open("export-3.geojson", "r") as f:
    data = json.load(f)

output = []

for feature in data["features"]:
    props = feature.get("properties", {})
    coords = feature["geometry"]["coordinates"]

    name = props.get("name")
    if not name:
        continue

    osm_type = props.get("shop") or props.get("amenity")
    category = CATEGORY_MAP.get(osm_type, "other")

    output.append({
        "name": name,
        "lat": coords[1],
        "lon": coords[0],
        "category": category
    })

with open("export-3.geojson", "w") as f:
    json.dump(output, f, indent=2)
