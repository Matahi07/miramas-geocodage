import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import requests
import json
from io import BytesIO
import tempfile
import os
import zipfile
import branca

st.set_page_config(
    page_title="Géocodage – Ville de Miramas",
    page_icon="📍",
    layout="wide",
    initial_sidebar_state="expanded"
)
st.title("🗺️ Application complète de géocodage – Miramas")

API_KEY = "3b2890debe91403dad9986b2799b8714"

uploaded_file = st.file_uploader("📤 Téléversez un fichier Excel avec les adresses", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file, sheet_name="Clos de Craponne et Val Auré", skiprows=2)
    df.columns = [
        "parcelle", "nom_prenom", "situation", "voie_origine",
        "adresse_origine", "numero_nouvelle", "voie_nouvelle", "adresse_election"
    ]

    df = df.dropna(subset=["numero_nouvelle", "voie_nouvelle"])
    df["ville"] = "Miramas"
    df["pays"] = "France"
    df["numero_nouvelle"] = df["numero_nouvelle"].astype(str).str.strip()
    df["voie_nouvelle"] = df["voie_nouvelle"].astype(str).str.strip()
    df["adresse_complete"] = df["numero_nouvelle"] + " " + df["voie_nouvelle"] + ", Miramas, France"

    st.success("✅ Données préparées")
    st.dataframe(df[["adresse_complete"]].head(10))

    if st.button("📍 Lancer le géocodage avec OpenCage"):
        latitudes, longitudes = [], []
        progress = st.progress(0)
        for i, adresse in enumerate(df["adresse_complete"]):
            url = "https://api.opencagedata.com/geocode/v1/json"
            params = {
                'q': adresse,
                'key': API_KEY,
                'limit': 1,
                'language': 'fr',
                'no_annotations': 1
            }
            try:
                response = requests.get(url, params=params)
                data = response.json()
                if data and data["results"]:
                    lat = data["results"][0]["geometry"]["lat"]
                    lon = data["results"][0]["geometry"]["lng"]
                    latitudes.append(lat)
                    longitudes.append(lon)
                else:
                    latitudes.append(None)
                    longitudes.append(None)
            except:
                latitudes.append(None)
                longitudes.append(None)
            progress.progress((i + 1) / len(df))
        df["latitude"] = pd.to_numeric(latitudes, errors="coerce")
        df["longitude"] = pd.to_numeric(longitudes, errors="coerce")
        st.session_state["df_geo"] = df

if "df_geo" in st.session_state:
    df = st.session_state["df_geo"]

    st.markdown("### 📋 Données géocodées")
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

    map_html = folium_map.get_root().render()
    st.components.v1.html(map_html, height=500)

    st.markdown("### 📁 Télécharger les résultats")

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Télécharger CSV", csv, "adresses.csv", "text/csv")

    geojson = {
        "type": "FeatureCollection",
        "features": []
    }
    for _, row in df.dropna(subset=["latitude", "longitude"]).iterrows():
        geojson["features"].append({
            "type": "Feature",
            "properties": {"adresse": row["adresse_complete"]},
            "geometry": {
                "type": "Point",
                "coordinates": [row["longitude"], row["latitude"]]
            }
        })
    geojson_bytes = json.dumps(geojson, ensure_ascii=False).encode("utf-8")
    st.download_button("⬇️ Télécharger GeoJSON", geojson_bytes, "adresses.geojson", "application/geo+json")

    # Excel
    excel_output = BytesIO()
    with pd.ExcelWriter(excel_output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Adresses")
    st.download_button("⬇️ Télécharger Excel", excel_output.getvalue(), "adresses.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # GeoPackage
    gdf = gpd.GeoDataFrame(df.dropna(subset=["latitude", "longitude"]).copy(),
                           geometry=gpd.points_from_xy(df["longitude"], df["latitude"]),
                           crs="EPSG:4326")
    gpkg_buffer = BytesIO()
    with tempfile.TemporaryDirectory() as tmpdir:
        gpkg_path = os.path.join(tmpdir, "adresses.gpkg")
        gdf.to_file(gpkg_path, driver="GPKG")
        with open(gpkg_path, "rb") as f:
            gpkg_buffer.write(f.read())
    st.download_button("⬇️ Télécharger GeoPackage", gpkg_buffer.getvalue(), "adresses.gpkg", "application/geopackage+sqlite3")

    # Shapefile ZIP
    with tempfile.TemporaryDirectory() as tmpdir:
        shp_path = os.path.join(tmpdir, "adresses.shp")
        gdf.to_file(shp_path)
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            for ext in [".shp", ".shx", ".dbf", ".prj", ".cpg"]:
                fpath = shp_path.replace(".shp", ext)
                if os.path.exists(fpath):
                    zf.write(fpath, arcname=os.path.basename(fpath))
        zip_buffer.seek(0)
        st.download_button("⬇️ Télécharger Shapefile (ZIP)", zip_buffer.getvalue(), "adresses_shapefile.zip", "application/zip")
