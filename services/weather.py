import os

import requests

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "YOUR_OPENWEATHER_API_KEY")


def get_weather(location: str) -> str:
    if not location:
        return "I do not know your location yet. Please update it first."

    params = {
        "q": location,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric",
    }
    try:
        response = requests.get("https://api.openweathermap.org/data/2.5/weather", params=params, timeout=8)
        response.raise_for_status()
        data = response.json()
        temp = data.get("main", {}).get("temp")
        description = data.get("weather", [{}])[0].get("description", "weather conditions")
        if temp is not None:
            return f"The weather in {location} is {temp}°C with {description}."
        return f"I could not retrieve detailed weather data for {location}."
    except requests.RequestException:
        return f"Weather data for {location} is currently unavailable. Please try again later."
