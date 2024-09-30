import streamlit as st
import requests
import folium
from streamlit_folium import folium_static
import google.generativeai as genai
import json
from typing import List, Dict, Any
import asyncio
import aiohttp
from collections import Counter

# Configure Gemini API using Streamlit secrets
if 'GOOGLE_API_KEY' not in st.secrets:
  st.error("GOOGLE_API_KEY not found in Streamlit secrets. Please add it to your secrets.toml file.")
  st.stop()

genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
model = genai.GenerativeModel('gemini-pro')

async def fetch_geojson_data(session: aiohttp.ClientSession, api_url: str) -> Dict[str, Any]:
  """Fetch GeoJSON data from a given URL asynchronously."""
  async with session.get(api_url) as response:
      response.raise_for_status()
      data = await response.json()
      
      # Check if the response is in the ArcGIS REST API format
      if 'features' in data and 'geometryType' in data:
          # Convert ArcGIS JSON to GeoJSON
          geojson = {
              "type": "FeatureCollection",
              "features": data['features']
          }
          return geojson
      return data

def create_map(geojson_data: Dict[str, Any], center: List[float], zoom: int = 10) -> folium.Map:
  """Create a folium map with the provided GeoJSON data."""
  m = folium.Map(location=center, zoom_start=zoom)
  folium.GeoJson(
      geojson_data, 
      name="GeoJSON Layer",
      style_function=lambda feature: {
          'fillColor': 'green',
          'color': 'black',
          'weight': 2,
          'fillOpacity': 0.7,
      }
  ).add_to(m)
  folium.LayerControl().add_to(m)
  return m

def analyze_geojson_structure(geojson_data: Dict[str, Any]) -> Dict[str, Any]:
  """Analyze the structure of the GeoJSON data and return available properties."""
  all_properties = set()
  property_types = {}
  sample_values = {}
  
  for feature in geojson_data.get('features', []):
      properties = feature.get('properties', {})
      all_properties.update(properties.keys())
      
      for key, value in properties.items():
          if key not in property_types:
              property_types[key] = type(value).__name__
          if key not in sample_values:
              sample_values[key] = str(value)
  
  return {
      "properties": sorted(list(all_properties)),
      "property_types": property_types,
      "sample_values": sample_values
  }

def count_features_by_property(geojson_data: Dict[str, Any], property_name: str, property_value: str) -> int:
  """Count features in the GeoJSON data based on a specific property and value."""
  count = sum(1 for feature in geojson_data.get('features', [])
              if str(feature.get('properties', {}).get(property_name, '')).lower() == property_value.lower())
  return count

def process_query(prompt: str, geojson_data: Dict[str, Any], geojson_structure: Dict[str, Any]) -> str:
  """Process user query using Gemini API and geospatial data."""
  context = f"You are a geospatial data expert. The user has provided a GeoJSON dataset with the following properties: {', '.join(geojson_structure['properties'])}. "
  context += "Analyze the query and provide insights based on the geospatial data available."

  # Check if the query is about counting
  if "how many" in prompt.lower() or "count" in prompt.lower():
      for prop in geojson_structure['properties']:
          if prop.lower() in prompt.lower():
              # Try to extract a value for this property from the query
              words = prompt.lower().split()
              prop_index = words.index(prop.lower())
              if prop_index < len(words) - 1:
                  value = words[prop_index + 1]
                  count = count_features_by_property(geojson_data, prop, value)
                  return f"Based on the analysis, there are {count} features where {prop} is {value}."

  # If no specific count query is detected, pass the query to Gemini
  chat = model.start_chat(history=[])
  response = chat.send_message(f"{context}\n\nUser query: {prompt}\n\nGeoJSON structure: {json.dumps(geojson_structure)}")
  
  return response.text

def main():
  st.set_page_config(page_title="Geospatial Data Chatbot", layout="wide")
  st.title("Geospatial Data Chatbot")
  
  # Initialize session state
  if "messages" not in st.session_state:
      st.session_state.messages = []
  if "geojson_data" not in st.session_state:
      st.session_state.geojson_data = None
  if "geojson_structure" not in st.session_state:
      st.session_state.geojson_structure = None

  # Create two columns
  col1, col2 = st.columns([2, 1])

  with col1:
      # GeoJSON input section
      st.subheader("Enter a GeoJSON URL:")
      url_input = st.text_input("GeoJSON URL")

      if st.button("Load GeoJSON"):
          if url_input:
              with st.spinner("Loading GeoJSON data..."):
                  async def load_data():
                      async with aiohttp.ClientSession() as session:
                          return await fetch_geojson_data(session, url_input)
                  st.session_state.geojson_data = asyncio.run(load_data())
                  st.session_state.geojson_structure = analyze_geojson_structure(st.session_state.geojson_data)
              st.success("GeoJSON data loaded successfully.")
          else:
              st.error("Please specify a valid GeoJSON URL.")

      # Display available properties
      if st.session_state.geojson_structure:
          st.subheader("Available Properties:")
          for prop in st.session_state.geojson_structure['properties']:
              st.write(f"- {prop} (Type: {st.session_state.geojson_structure['property_types'][prop]}, e.g., {st.session_state.geojson_structure['sample_values'][prop]})")

      # Visualization section
      if st.session_state.geojson_data:
          st.subheader("Visualize GeoJSON")
          center_lat = st.number_input("Center Latitude", value=39.0)
          center_lon = st.number_input("Center Longitude", value=-76.7)
          zoom_level = st.slider("Zoom Level", min_value=1, max_value=18, value=10)
          
          if st.button("Create Map"):
              with st.spinner("Creating map..."):
                  folium_map = create_map(st.session_state.geojson_data, center=[center_lat, center_lon], zoom=zoom_level)
                  folium_static(folium_map, width=700, height=500)

  with col2:
      # Chat interface
      st.subheader("Chat with the Geospatial Data Expert")
      if st.session_state.geojson_structure:
          st.write("You can ask questions about the loaded GeoJSON data. For example:")
          st.write("- How many features are there where [property] is [value]?")
          st.write("- What can you tell me about the [property] in this dataset?")

      if prompt := st.chat_input("What would you like to know about the geospatial data?"):
          st.chat_message("user").markdown(prompt)
          st.session_state.messages.append({"role": "user", "content": prompt})

          if st.session_state.geojson_data:
              with st.spinner("Processing your query..."):
                  response = process_query(prompt, st.session_state.geojson_data, st.session_state.geojson_structure)
              with st.chat_message("assistant"):
                  st.markdown(response)
              st.session_state.messages.append({"role": "assistant", "content": response})
          else:
              st.error("Please load GeoJSON data before asking questions.")

if __name__ == "__main__":
  main()

# Created/Modified files during execution:
# No files were created or modified during the execution of this script.
