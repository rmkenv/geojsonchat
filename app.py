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

def create_map(geojson_data_list: List[Dict[str, Any]], center: List[float], zoom: int = 10) -> folium.Map:
  """Create a folium map with the provided list of GeoJSON data."""
  m = folium.Map(location=center, zoom_start=zoom)
  for idx, geojson_data in enumerate(geojson_data_list):
      folium.GeoJson(
          geojson_data, 
          name=f"GeoJSON Layer {idx+1}",
          style_function=lambda feature: {
              'fillColor': 'green',
              'color': 'black',
              'weight': 2,
              'fillOpacity': 0.7,
          }
      ).add_to(m)
  folium.LayerControl().add_to(m)
  return m

def analyze_geojson(geojson_data_list: List[Dict[str, Any]], query: str) -> str:
  """Analyze GeoJSON data based on the query."""
  query_lower = query.lower()
  
  # Identify potential key words in the query
  count_keywords = ["how many", "count", "number of"]
  
  if any(keyword in query_lower for keyword in count_keywords):
      # This is likely a counting query
      # Try to identify what we're counting and any potential filters
      features_to_count = []
      for geojson in geojson_data_list:
          features_to_count.extend(geojson.get('features', []))
      
      # Analyze the properties of the first feature to understand the data structure
      if features_to_count:
          sample_properties = features_to_count[0].get('properties', {})
          property_counts = Counter()
          
          for feature in features_to_count:
              properties = feature.get('properties', {})
              for key, value in properties.items():
                  if isinstance(value, (str, int, float)):
                      property_counts[f"{key}:{value}"] += 1
          
          # Find the most common property values that might match the query
          potential_matches = [item for item, count in property_counts.most_common(5)]
          
          # Try to match these with the query
          for match in potential_matches:
              if match.lower() in query_lower:
                  key, value = match.split(':')
                  count = sum(1 for feature in features_to_count if feature.get('properties', {}).get(key) == value)
                  return f"Based on the analysis, there are {count} features where {key} is {value}."
          
          # If no specific match, return total count
          return f"The total number of features across all provided GeoJSON datasets is {len(features_to_count)}."
  
  return "I couldn't perform a specific analysis for this query. Please try asking about counts or numbers of specific features or properties in the data."

def process_query(prompt: str, geojson_data_list: List[Dict[str, Any]]) -> str:
  """Process user query using Gemini API and geospatial data."""
  context = f"You are a geospatial data expert. The user has provided {len(geojson_data_list)} GeoJSON datasets. "
  context += "Analyze the query and provide insights based on the geospatial data available."
  
  # Prepare a summary of the data for the AI
  data_summary = []
  for idx, geojson in enumerate(geojson_data_list):
      feature_count = len(geojson.get('features', []))
      if feature_count > 0:
          sample_properties = geojson['features'][0].get('properties', {})
          data_summary.append(f"Dataset {idx+1}: {feature_count} features. Sample properties: {list(sample_properties.keys())}")
  
  data_summary_str = "\n".join(data_summary)
  
  # Perform data analysis
  analysis_result = analyze_geojson(geojson_data_list, prompt)

  # Prepare the prompt for the AI
  ai_prompt = f"{context}\n\nData Summary:\n{data_summary_str}\n\nUser query: {prompt}\n\nAnalysis result: {analysis_result}"

  # Get response from Gemini
  chat = model.start_chat(history=[])
  response = chat.send_message(ai_prompt)
  
  return f"{response.text}\n\n{analysis_result}"

async def load_geojsons(urls: List[str]) -> List[Dict[str, Any]]:
  """Load GeoJSON data from multiple URLs asynchronously."""
  async with aiohttp.ClientSession() as session:
      tasks = [fetch_geojson_data(session, url) for url in urls if url.strip()]
      return await asyncio.gather(*tasks)

def main():
  st.set_page_config(page_title="Geospatial Data Chatbot", layout="wide")
  st.title("Geospatial Data Chatbot")
  
  # Initialize chat history and geojson data list in session state
  if "messages" not in st.session_state:
      st.session_state.messages = []
  if "geojson_data_list" not in st.session_state:
      st.session_state.geojson_data_list = []

  # Display chat messages from history on app rerun
  for message in st.session_state.messages:
      with st.chat_message(message["role"]):
          st.markdown(message["content"])

  # Create two columns
  col1, col2 = st.columns([2, 1])

  with col1:
      # GeoJSON input section
      st.subheader("Enter up to 5 GeoJSON URLs:")
      url_inputs = [st.text_input(f"GeoJSON URL {i+1}", key=f"url_{i}") for i in range(5)]

      area_of_interest = st.text_input("Enter Area of Interest (Latitude, Longitude)", "39.0, -76.7")

      if st.button("Load GeoJSONs"):
          valid_urls = [url for url in url_inputs if url.strip()]

          if valid_urls:
              with st.spinner("Loading GeoJSON data..."):
                  st.session_state.geojson_data_list = asyncio.run(load_geojsons(valid_urls))
              st.success(f"Loaded {len(st.session_state.geojson_data_list)} GeoJSON datasets.")
          else:
              st.error("Please specify at least one valid GeoJSON URL.")

      # Visualization section
      if st.button("Visualize GeoJSONs"):
          if st.session_state.geojson_data_list and area_of_interest:
              try:
                  coords = area_of_interest.split(",")
                  if len(coords) != 2:
                      raise ValueError("Invalid coordinates format")
                  lat, lon = map(float, coords)
                  center = [lat, lon]
                  with st.spinner("Creating map..."):
                      folium_map = create_map(st.session_state.geojson_data_list, center=center)
                      folium_static(folium_map, width=800, height=600)
              except ValueError:
                  st.error("Please enter valid coordinates in the format: Latitude, Longitude")
          else:
              st.error("Please load GeoJSON data and specify an area of interest first.")

  with col2:
      # Chat interface
      st.subheader("Chat with the Geospatial Data Expert")
      if prompt := st.chat_input("What would you like to know about the geospatial data?"):
          st.chat_message("user").markdown(prompt)
          st.session_state.messages.append({"role": "user", "content": prompt})

          if st.session_state.geojson_data_list:
              with st.spinner("Processing your query..."):
                  response = process_query(prompt, st.session_state.geojson_data_list)
              with st.chat_message("assistant"):
                  st.markdown(response)
              st.session_state.messages.append({"role": "assistant", "content": response})
          else:
              st.error("Please load GeoJSON data before asking questions.")

if __name__ == "__main__":
  main()

# Created/Modified files during execution:
# No files were created or modified during the execution of this script.
