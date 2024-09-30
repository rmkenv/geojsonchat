import streamlit as st
import requests
import folium
from streamlit_folium import folium_static
import geopandas as gpd
from shapely.geometry import Point, Polygon
import pandas as pd

def fetch_geojson_data(api_url, query_params):
    """Fetch GeoJSON data from a given API based on query parameters."""
    response = requests.get(api_url, params=query_params)
    return response.json()

def create_map(geojson_data, center, zoom=10):
    """Create a folium map with the provided GeoJSON data."""
    m = folium.Map(location=center, zoom_start=zoom)
    folium.GeoJson(geojson_data, name="geojson").add_to(m)
    return m

def main():
    st.title("Geospatial Data Chatbot")

    # User inputs for analysis type and area of interest
    analysis_type = st.selectbox("Select Analysis Type", ["Solar Potential", "Vegetation Index", "Population Density"])
    area_of_interest = st.text_input("Enter Area of Interest", "Latitude, Longitude")

    if st.button("Analyze"):
        if area_of_interest:
            try:
                # Example coordinates split and converted
                lat, lon = map(float, area_of_interest.split(","))
            except ValueError:
                st.error("Please enter valid coordinates in the format: Latitude, Longitude")
                return
            
            # Example API URL (this would be your actual GeoJSON API endpoint)
            api_url = "https://your-api-domain.com/geojson"
            query_params = {
                "lat": lat,
                "lon": lon,
                "type": analysis_type.lower()
            }

            # Fetching data
            geojson_data = fetch_geojson_data(api_url, query_params)
            
            # Creating map
            folium_map = create_map(geojson_data, center=[lat, lon])
            folium_static(folium_map)
        else:
            st.error("Please specify an area of interest.")

if __name__ == "__main__":
    main()
