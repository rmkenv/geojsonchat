import streamlit as st
import requests
import folium
from streamlit_folium import folium_static
import google.generativeai as genai
import json

# Configure Gemini API using Streamlit secrets
if 'GOOGLE_API_KEY' not in st.secrets:
  st.error("GOOGLE_API_KEY not found in Streamlit secrets. Please add it to your secrets.toml file.")
  st.stop()

genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
model = genai.GenerativeModel('gemini-pro')

def fetch_geojson_data(api_url):
  """Fetch GeoJSON data from a given URL."""
  response = requests.get(api_url)
  response.raise_for_status()
  data = response.json()
  
  # Check if the response is in the ArcGIS REST API format
  if 'features' in data and 'geometryType' in data:
      # Convert ArcGIS JSON to GeoJSON
      geojson = {
          "type": "FeatureCollection",
          "features": data['features']
      }
      return geojson
  return data

def create_map(geojson_data_list, center, zoom=10):
  """Create a folium map with the provided list of GeoJSON data."""
  m = folium.Map(location=center, zoom_start=zoom)
  for idx, geojson_data in enumerate(geojson_data_list):
      folium.GeoJson(geojson_data, name=f"GeoJSON Layer {idx+1}").add_to(m)
  folium.LayerControl().add_to(m)
  return m

def process_query(prompt, geojson_data_list):
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
  
  chat = model.start_chat(history=[])
  response = chat.send_message(f"{context}\n\nData Summary:\n{data_summary_str}\n\nUser query: {prompt}")
  return response.text

def main():
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

  # GeoJSON input section
  st.subheader("Enter up to 5 GeoJSON URLs:")
  url_inputs = [st.text_input(f"GeoJSON URL {i+1}", key=f"url_{i}") for i in range(5)]

  area_of_interest = st.text_input("Enter Area of Interest (Latitude, Longitude)", "39.0, -76.7")

  if st.button("Load GeoJSONs"):
      st.session_state.geojson_data_list = []
      valid_urls = [url for url in url_inputs if url.strip()]

      if valid_urls:
          for url in valid_urls:
              try:
                  with st.spinner(f"Loading data from {url}..."):
                      data = fetch_geojson_data(url)
                      st.session_state.geojson_data_list.append(data)
              except requests.exceptions.RequestException as e:
                  st.error(f"Failed to fetch data from {url}: {str(e)}")
          
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
                folium_static(folium_map)
        except ValueError:
            st.error("Please enter valid coordinates in the format: Latitude, Longitude")
    else:
        st.error("Please load GeoJSON data and specify an area of interest first.")


  # Chat interface
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
