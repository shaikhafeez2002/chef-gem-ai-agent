import json
import os
import urllib.parse
import urllib.request


def geocode_address(address: str) -> str:
    """Geocode a physical address or city name into latitude/longitude coordinates using Google Maps Geocoding API.

    Args:
        address: Street address, city, or location name (e.g. '1600 Amphitheatre Pkwy, Mountain View, CA' or 'San Francisco, CA').

    Returns:
        Latitude, longitude, formatted address, and location details.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    if not api_key:
        return "Error: GOOGLE_MAPS_API_KEY environment variable is not set."

    encoded_address = urllib.parse.quote(address)
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={encoded_address}&key={api_key}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AntigravityPersonalChef/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            status = data.get("status")
            if status != "OK" or not data.get("results"):
                return f"Geocoding failed for address '{address}' (Status: {status})."

            first_result = data["results"][0]
            fmt_address = first_result.get("formatted_address")
            location = first_result.get("geometry", {}).get("location", {})
            lat = location.get("lat")
            lng = location.get("lng")

            return (
                f"📍 **Geocoding Result**\n"
                f"  - Address: {fmt_address}\n"
                f"  - Location: Latitude {lat}, Longitude {lng}\n"
                f"  - Coordinates: ({lat}, {lng})"
            )
    except Exception as e:
        return f"Error executing Geocoding API request: {e}"


def find_nearby_places(latitude: float, longitude: float, place_type: str = "grocery_store", radius_meters: float = 5000.0) -> str:
    """Find nearby places (e.g. grocery stores, supermarkets, restaurants) around coordinates using Google Places API (New).

    Args:
        latitude: Center latitude coordinate (e.g. 37.7749).
        longitude: Center longitude coordinate (e.g. -122.4194).
        place_type: Type of place to search for (e.g. 'grocery_store', 'supermarket', 'restaurant', 'bakery').
        radius_meters: Search radius in meters (default 5000m / 5km).

    Returns:
        List of nearby places with name, formatted address, and location coordinates.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    if not api_key:
        return "Error: GOOGLE_MAPS_API_KEY environment variable is not set."

    url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location,places.types,places.rating"
    }

    body = {
        "includedTypes": [place_type],
        "locationRestriction": {
            "circle": {
                "center": {
                    "latitude": float(latitude),
                    "longitude": float(longitude)
                },
                "radius": float(radius_meters)
            }
        }
    }

    try:
        req_data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            places = data.get("places", [])
            if not places:
                return f"No nearby places of type '{place_type}' found within {radius_meters}m of ({latitude}, {longitude})."

            out = [f"Found {len(places)} nearby '{place_type}' location(s):\n"]
            for p in places[:5]:
                name = p.get("displayName", {}).get("text", "Unknown Name")
                fmt_addr = p.get("formattedAddress", "N/A")
                loc = p.get("location", {})
                lat = loc.get("latitude")
                lng = loc.get("longitude")
                rating = p.get("rating", "N/A")

                out.append(
                    f"🏪 **{name}** (Rating: {rating})\n"
                    f"   - Address: {fmt_addr}\n"
                    f"   - Location: ({lat}, {lng})\n"
                )
            return "\n".join(out)
    except Exception as e:
        return f"Error executing Places API (New) searchNearby request: {e}"
