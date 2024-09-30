import streamlit as st
import requests
import folium
from streamlit_folium import folium_static
import geopandas as gpd
from shapely.geometry import Point, Polygon
import pandas as pd

def fetch_geojson_data(api_url):
  """Fetch GeoJSON data from a given URL."""
  response = requests.get(api_url)
  response.raise_for_status()  # Raise an exception for bad responses
  return response.json()

def create_map(geojson_data_list, center, zoom=10):
  """Create a folium map with the provided list of GeoJSON data."""
  m = folium.Map(location=center, zoom_start=zoom)
  for idx, geojson_data in enumerate(geojson_data_list):
      folium.GeoJson(geojson_data, name=f"GeoJSON Layer {idx+1}").add_to(m)
  folium.LayerControl().add_to(m)
  return m

def main():
  st.title("Geospatial Data Chatbot")
  
  st.subheader("Enter up to 5 GeoJSON URLs:")
  url_inputs = [st.text_input(f"GeoJSON URL {i+1}", key=f"url_{i}") for i in range(5)]

  area_of_interest = st.text_input("Enter Area of Interest (Latitude, Longitude)", "0, 0")

  if st.button("Visualize GeoJSONs"):
      geojson_data_list = []
      valid_urls = [url for url in url_inputs if url.strip()]

      if valid_urls and area_of_interest:
          try:
              lat, lon = map(float, area_of_interest.split(","))
              center = [lat, lon]
          except ValueError:
              st.error("Please enter valid coordinates in the format: Latitude, Longitude")
              return
          
          for url in valid_urls:
              try:
                  data = fetch_geojson_data(url)
                  geojson_data_list.append(data)
              except requests.exceptions.RequestException as e:
                  st.error(f"Failed to fetch data from {url}: {str(e)}")
          
          if geojson_data_list:
              folium_map = create_map(geojson_data_list, center=center)
              folium_static(folium_map)
          else:
              st.error("No valid GeoJSON data to display.")
      else:
          st.error("Please specify at least one valid GeoJSON URL and area of interest.")

if __name__ == "__main__":
  main()

# Created/Modified files during execution:
# No files were created or modified during the execution of this script.
