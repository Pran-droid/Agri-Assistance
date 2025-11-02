import requests
from typing import Dict, List, Optional
from datetime import datetime


# Data.gov.in API configuration
MARKET_API_URL = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
API_KEY = "579b464db66ec23bdd00000122bf35ef5cef4bb5405747991b0b1ede"

# Common city to district/state mappings for better location matching
CITY_DISTRICT_MAP = {
    # Major cities and their districts
    "delhi": {"district": "Delhi", "state": "Delhi"},
    "new delhi": {"district": "Delhi", "state": "Delhi"},
    "mumbai": {"district": "Mumbai", "state": "Maharashtra"},
    "pune": {"district": "Pune", "state": "Maharashtra"},
    "bangalore": {"district": "Bangalore", "state": "Karnataka"},
    "bengaluru": {"district": "Bangalore", "state": "Karnataka"},
    "hyderabad": {"district": "Hyderabad", "state": "Telangana"},
    "chennai": {"district": "Chennai", "state": "Tamil Nadu"},
    "kolkata": {"district": "Kolkata", "state": "West Bengal"},
    "ahmedabad": {"district": "Ahmedabad", "state": "Gujarat"},
    "jaipur": {"district": "Jaipur", "state": "Rajasthan"},
    "lucknow": {"district": "Lucknow", "state": "Uttar Pradesh"},
    "kanpur": {"district": "Kanpur", "state": "Uttar Pradesh"},
    "nagpur": {"district": "Nagpur", "state": "Maharashtra"},
    "indore": {"district": "Indore", "state": "Madhya Pradesh"},
    "bhopal": {"district": "Bhopal", "state": "Madhya Pradesh"},
    "patna": {"district": "Patna", "state": "Bihar"},
    "chandigarh": {"district": "Chandigarh", "state": "Chandigarh"},
    "surat": {"district": "Surat", "state": "Gujarat"},
    "vadodara": {"district": "Vadodara", "state": "Gujarat"},
    "coimbatore": {"district": "Coimbatore", "state": "Tamil Nadu"},
    "kochi": {"district": "Ernakulam", "state": "Kerala"},
    "cochin": {"district": "Ernakulam", "state": "Kerala"},
    "thiruvananthapuram": {"district": "Thiruvananthapuram", "state": "Kerala"},
    "trivandrum": {"district": "Thiruvananthapuram", "state": "Kerala"},
    "visakhapatnam": {"district": "Visakhapatnam", "state": "Andhra Pradesh"},
    "vijayawada": {"district": "Krishna", "state": "Andhra Pradesh"},
    "mysore": {"district": "Mysore", "state": "Karnataka"},
    "mysuru": {"district": "Mysore", "state": "Karnataka"},
}


def parse_location(location: str) -> Dict[str, Optional[str]]:
    """
    Parse user's location (city or "District, State" format) to district and state for API query.
    
    Args:
        location: User's location string (city name or "District, State" format)
    
    Returns:
        Dictionary with 'district' and 'state' keys
    """
    if not location:
        return {"district": None, "state": None}
    
    location_lower = location.lower().strip()
    
    # Check if location is in "District, State" format
    if "," in location:
        parts = [part.strip() for part in location.split(",")]
        if len(parts) == 2:
            return {"district": parts[0], "state": parts[1]}
    
    # Check if it's a known city
    if location_lower in CITY_DISTRICT_MAP:
        return CITY_DISTRICT_MAP[location_lower]
    
    # Otherwise, try to use it as both district and state search term
    return {"district": location, "state": None}


def fetch_market_data(state: Optional[str] = None, district: Optional[str] = None, commodity: Optional[str] = None, limit: int = 100) -> Dict:
    """
    Fetch market price data from data.gov.in API.
    
    Args:
        state: Filter by state name (optional)
        district: Filter by district name (optional)
        commodity: Filter by commodity name (optional)
        limit: Maximum number of records to fetch
    
    Returns:
        Dictionary containing market data with records, updated date, and description
    """
    params = {
        "api-key": API_KEY,
        "format": "json",
        "offset": 0,
        "limit": limit
    }
    
    # The API doesn't support server-side filtering via filters parameter
    # We'll fetch data and filter client-side
    
    try:
        response = requests.get(MARKET_API_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Client-side filtering
        if data and "records" in data:
            records = data["records"]
            filtered_records = records
            
            # Filter by state
            if state:
                filtered_records = [
                    r for r in filtered_records
                    if state.upper() in r.get("state", "").upper()
                ]
            
            # Filter by district
            if district:
                filtered_records = [
                    r for r in filtered_records
                    if district.upper() in r.get("district", "").upper()
                ]
            
            # Filter by commodity
            if commodity:
                filtered_records = [
                    r for r in filtered_records
                    if commodity.upper() in r.get("commodity", "").upper()
                ]
            
            data["records"] = filtered_records
        
        return data
    except requests.RequestException as e:
        print(f"Error fetching market data: {e}")
        return {"records": [], "updated_date": None, "desc": "Unable to fetch market data"}


def format_market_prices(records: List[Dict], location: str = "", district: str = "", state: str = "", top_n: int = 10) -> str:
    """
    Format market price records into a readable text response.
    
    Args:
        records: List of market price records
        location: User's location for display
        district: District name for filtering (already filtered from API)
        state: State name for filtering (already filtered from API)
        top_n: Number of top results to show
    
    Returns:
        Formatted string with market prices
    """
    if not records:
        return f"No market price data available for {location or 'your region'}."
    
    # Records are already filtered by API, just take top N
    filtered_records = records[:top_n]
    
    if location:
        result = f"Market prices for {location}:\n\n"
    else:
        result = "Market prices:\n\n"
    
    # Format each record
    for i, record in enumerate(filtered_records, 1):
        state_name = record.get("state", "N/A")
        district_name = record.get("district", "N/A")
        market = record.get("market", "N/A")
        commodity = record.get("commodity", "N/A")
        variety = record.get("variety", "N/A")
        min_price = record.get("min_price", "N/A")
        max_price = record.get("max_price", "N/A")
        modal_price = record.get("modal_price", "N/A")
        
        result += f"{i}. **{commodity}** ({variety})\n"
        result += f"   📍 Location: {market}, {district_name}, {state_name}\n"
        result += f"   💰 Price Range: ₹{min_price} - ₹{max_price}\n"
        result += f"   📊 Modal Price: ₹{modal_price}\n\n"
    
    return result.strip()


def get_market_prices(location: str) -> str:
    """
    Get current market prices for commodities based on user's location.
    
    Args:
        location: User's location (city name)
    
    Returns:
        Formatted string with market price information
    """
    location_text = location or "India"
    
    try:
        # Parse location to get district and state
        location_info = parse_location(location)
        district = location_info.get("district")
        state = location_info.get("state")
        
        print(f"📍 Searching market prices for: {location} -> District: {district}, State: {state}")
        
        # Try to fetch data with district filter first
        data = None
        if district:
            data = fetch_market_data(district=district, state=state, limit=300)
            if data and data.get("records"):
                print(f"✅ Found {len(data['records'])} records for district: {district}")
        
        # If no district-specific data, try with state only
        if not data or not data.get("records"):
            if state:
                data = fetch_market_data(state=state, limit=300)
                if data and data.get("records"):
                    print(f"✅ Found {len(data['records'])} records for state: {state}")
        
        # If still no data, fetch general data
        if not data or not data.get("records"):
            data = fetch_market_data(limit=300)
            print(f"⚠️ Using general market data, {len(data.get('records', []))} records")
        
        if not data or "records" not in data:
            return f"Unable to fetch market prices for {location_text} at the moment. Please try again later."
        
        records = data.get("records", [])
        updated_date = data.get("updated_date")
        
        if not records:
            return f"No market price data available for {location_text}."
        
        # Format the response with location-specific filtering
        response = format_market_prices(
            records, 
            location=location_text,
            district=district or "",
            state=state or "",
            top_n=8
        )
        
        # Add update information
        if updated_date:
            try:
                update_dt = datetime.fromisoformat(updated_date.replace("Z", "+00:00"))
                response += f"\n\n📅 Last updated: {update_dt.strftime('%B %d, %Y')}"
            except:
                pass
        
        response += "\n\n💡 Tip: Prices vary by market. Visit your local mandi for exact rates."
        
        return response
        
    except Exception as e:
        print(f"Error in get_market_prices: {e}")
        return f"Error fetching market prices for {location_text}. The service may be temporarily unavailable."


def search_commodity_prices(commodity: str, location: Optional[str] = None) -> str:
    """
    Search for specific commodity prices.
    
    Args:
        commodity: Name of the commodity (e.g., "Tomato", "Rice", "Wheat")
        location: Optional location filter (city name)
    
    Returns:
        Formatted string with commodity-specific prices
    """
    try:
        # Parse location if provided
        district = None
        state = None
        if location:
            location_info = parse_location(location)
            district = location_info.get("district")
            state = location_info.get("state")
        
        # Fetch data for the commodity with higher limit to get more results
        data = fetch_market_data(commodity=commodity, district=district, state=state, limit=500)
        records = data.get("records", [])
        
        # If no records with district filter, try without it (state only)
        if not records and district:
            print(f"⚠️ No data for {commodity} in district {district}, trying state {state}")
            data = fetch_market_data(commodity=commodity, state=state, limit=500)
            records = data.get("records", [])
        
        # If still no records, try commodity only
        if not records:
            print(f"⚠️ No location-specific data, fetching all {commodity} prices")
            data = fetch_market_data(commodity=commodity, limit=500)
            records = data.get("records", [])
        
        if not records:
            return f"No price data found for {commodity}."
        
        return format_market_prices(
            records, 
            location=location or commodity,
            district=district or "",
            state=state or "",
            top_n=10
        )
        
    except Exception as e:
        print(f"Error searching commodity prices: {e}")
        return f"Error searching for {commodity} prices."


def get_state_market_summary(state: str) -> str:
    """
    Get market price summary for a specific state.
    
    Args:
        state: Name of the state
    
    Returns:
        Formatted summary of market prices in that state
    """
    try:
        data = fetch_market_data(state=state, limit=150)
        records = data.get("records", [])
        
        if not records:
            return f"No market data available for {state}."
        
        # Group by commodity and get average modal prices
        commodity_prices = {}
        for record in records:
            commodity = record.get("commodity", "Unknown")
            modal_price = record.get("modal_price")
            
            if modal_price and modal_price != "NR":
                try:
                    price = float(modal_price)
                    if commodity not in commodity_prices:
                        commodity_prices[commodity] = []
                    commodity_prices[commodity].append(price)
                except:
                    pass
        
        # Calculate averages
        result = f"Market Summary for {state}:\n\n"
        for commodity, prices in sorted(commodity_prices.items()):
            avg_price = sum(prices) / len(prices)
            result += f"• {commodity}: ₹{avg_price:.2f} (avg from {len(prices)} markets)\n"
        
        return result
        
    except Exception as e:
        print(f"Error getting state summary: {e}")
        return f"Error fetching market summary for {state}."
