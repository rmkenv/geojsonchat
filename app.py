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
import geopandas as gpd
from shapely.geometry import shape

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
      return await response.json()

def create_map(gdf: gpd.GeoDataFrame, center: List[float], zoom: int = 10) -> folium.Map:
  """Create a folium map with the provided GeoDataFrame."""
  m = folium.Map(location=center, zoom_start=zoom)
  folium.GeoJson(
      gdf.to_json(),
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

def analyze_geojson_structure(gdf: gpd.GeoDataFrame) -> Dict[str, Any]:
  """Analyze the structure of the GeoDataFrame and return available properties."""
  properties = gdf.columns.tolist()
  properties.remove('geometry')
  
  return {
      "properties": properties,
      "property_types": {prop: str(gdf[prop].dtype) for prop in properties},
      "sample_values": {prop: str(gdf[prop].iloc[0]) for prop in properties},
      "feature_count": len(gdf),
      "geometry_types": gdf.geometry.geom_type.value_counts().to_dict()
  }

def process_query(prompt: str, gdf: gpd.GeoDataFrame, geojson_structure: Dict[str, Any]) -> str:
  """Process user query using Gemini API and geospatial data."""
  context = (
      f"You are a geospatial data expert. The user has provided a GeoJSON dataset with the following properties: "
      f"{', '.join(geojson_structure['properties'])}. "
      f"The dataset contains {geojson_structure['feature_count']} features with geometry types: {geojson_structure['geometry_types']}. "
      "Analyze the query and provide insights based on the geospatial data available."
  )

  # Prepare some basic statistics
  stats = {
      "feature_count": len(gdf),
      "property_stats": {prop: gdf[prop].value_counts().to_dict() for prop in geojson_structure['properties'] if gdf[prop].dtype in ['object', 'int64', 'float64']}
  }

  # If the query is about counting or statistics
  if any(keyword in prompt.lower() for keyword in ["how many", "count", "average", "mean", "median", "sum"]):
      for prop in geojson_structure['properties']:
          if prop.lower() in prompt.lower():
              if gdf[prop].dtype in ['int64', 'float64']:
                  stats[f"{prop}_mean"] = gdf[prop].mean()
                  stats[f"{prop}_median"] = gdf[prop].median()
                  stats[f"{prop}_sum"] = gdf[prop].sum()
              value_counts = gdf[prop].value_counts()
              stats[f"{prop}_top_values"] = value_counts.head().to_dict()

  # Pass the query to Gemini along with the context and stats
  chat = model.start_chat(history=[])
  response = chat.send_message(
      f"{context}\n\nUser query: {prompt}\n\n"
      f"GeoJSON structure: {json.dumps(geojson_structure)}\n\n"
      f"Statistics: {json.dumps(stats)}"
  )
  
  return response.text

def main():
  st.set_page_config(page_title="GeoJSON Data Explorer", layout="wide")
  st.title("GeoJSON Data Explorer")
  
  # Initialize session state
  if "messages" not in st.session_state:
      st.session_state.messages = []
  if "gdf" not in st.session_state:
      st.session_state.gdf = None
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
                  try:
                      async def load_data():
                          async with aiohttp.ClientSession() as session:
                              return await fetch_geojson_data(session, url_input)
                      geojson_data = asyncio.run(load_data())
                      st.session_state.gdf = gpd.GeoDataFrame.from_features(geojson_data['features'])
                      st.session_state.geojson_structure = analyze_geojson_structure(st.session_state.gdf)
                      st.success("GeoJSON data loaded successfully.")
                  except Exception as e:
                      st.error(f"Failed to load GeoJSON data: {str(e)}")
                      st.session_state.gdf = None
                      st.session_state.geojson_structure = None
          else:
              st.error("Please specify a valid GeoJSON URL.")

      # Display available properties
      if st.session_state.geojson_structure:
          st.subheader("Dataset Overview:")
          st.write(f"Number of features: {st.session_state.geojson_structure['feature_count']}")
          st.write(f"Geometry types: {st.session_state.geojson_structure['geometry_types']}")
          st.subheader("Available Properties:")
          for prop in st.session_state.geojson_structure['properties']:
              st.write(f"- {prop} (Type: {st.session_state.geojson_structure['property_types'][prop]}, e.g., {st.session_state.geojson_structure['sample_values'][prop]})")

      # Visualization section
      if st.session_state.gdf is not None:
          st.subheader("Visualize GeoJSON")
          center_lat = st.number_input("Center Latitude", value=st.session_state.gdf.total_bounds[1])
          center_lon = st.number_input("Center Longitude", value=st.session_state.gdf.total_bounds[0])
          zoom_level = st.slider("Zoom Level", min_value=1, max_value=18, value=10)
          
          if st.button("Create Map"):
              with st.spinner("Creating map..."):
                  try:
                      folium_map = create_map(st.session_state.gdf, center=[center_lat, center_lon], zoom=zoom_level)
                      folium_static(folium_map, width=700, height=500)
                  except Exception as e:
                      st.error(f"Failed to create map: {str(e)}")

  with col2:
      # Chat interface
      st.subheader("Chat with the Geospatial Data Expert")
      if st.session_state.geojson_structure:
          st.write("You can ask questions about the loaded GeoJSON data. For example:")
          st.write("- How many features are there in total?")
          st.write("- What are the most common values for [property]?")
          st.write("- Can you summarize the data for me?")

      if prompt := st.chat_input("What would you like to know about the geospatial data?"):
          st.chat_message("user").markdown(prompt)
          st.session_state.messages.append({"role": "user", "content": prompt})

          if st.session_state.gdf is not None:
              with st.spinner("Processing your query..."):
                  try:
                      response = process_query(prompt, st.session_state.gdf, st.session_state.geojson_structure)
                      with st.chat_message("assistant"):
                          st.markdown(response)
                      st.session_state.messages.append({"role": "assistant", "content": response})
                  except Exception as e:
                      st.error(f"Failed to process query: {str(e)}")
          else:
              st.error("Please load GeoJSON data before asking questions.")

if __name__ == "__main__":
  main()

# Created/Modified files during execution:
# No files were created or modified during the execution of this script.
