import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import json
from io import BytesIO

st.set_page_config(layout="wide")
st.title("🗺️ Géocodage des adresses à Miramas")

if "df_geo" not in st.session_state:
    st.warning("Aucune donnée géocodée disponible.")
    st.stop()

df = st.session_state["df_geo"]

search = st.text_input("🔍 Rechercher une adresse")
if search:
    df = df[df["adresse_complete"].str.contains(search, case=False, na=False)]

st.dataframe(df[["adresse_complete", "latitude", "longitude"]])

basemap = st.selectbox("🗺️ Choisir le fond de carte", [
    "OpenStreetMap",
    "Esri World Imagery",
    "CartoDB Positron"
])

map_center = [43.5861, 5.0016]

tiles = basemap
attr = None
if basemap == "Esri World Imagery":
    tiles = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
    attr = "Tiles © Esri"
elif basemap == "CartoDB Positron":
    tiles = "CartoDB Positron"
    attr = "© OpenStreetMap, CartoDB"

folium_map = folium.Map(location=map_center, zoom_start=15, max_zoom=21, tiles=tiles, attr=attr)
cluster = MarkerCluster(options={"disableClusteringAtZoom": 17}).add_to(folium_map)

for _, row in df.dropna(subset=["latitude", "longitude"]).iterrows():
    folium.Marker(
        location=[float(row["latitude"]), float(row["longitude"])],
        popup=row["adresse_complete"]
    ).add_to(cluster)

st_folium(folium_map, width=700, height=500)
