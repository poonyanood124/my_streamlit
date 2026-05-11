import os

import certifi
import pandas as pd
import plotly.express as px
import streamlit as st
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError

st.set_page_config(page_title="Mini Airbnb", layout="wide")
st.markdown("""
<style>
    .stApp {
        background-color: #f7f9fc;
    }

    /* Sidebar light blue */
    section[data-testid="stSidebar"] {
        background-color: #dbeeff;
    }

    /* clean text */
    h1, h2, h3 {
        color: #333;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

st.title("Mini Airbnb Dashboard")

@st.cache_resource
def init_connection():
    uri = st.secrets.get("MONGODB_URI") or os.getenv("MONGODB_URI")
    if not uri:
        st.error("Missing MONGODB_URI. Add it to Streamlit secrets or environment variables.")
        st.stop()
    try:
        client = MongoClient(
            uri,
            tls=True,
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=10000,
        )
        client.admin.command("ping")
        return client
    except ServerSelectionTimeoutError as exc:
        st.error("Could not connect to MongoDB Atlas.")
        st.info(
            "If you are running locally with macOS system Python, upgrade to Python 3.11+ "
            "or use a virtual environment built from a newer Python release."
        )
        st.code(str(exc))
        st.stop()

client = init_connection()
db = client["sample_airbnb"]
collection = db["listingsAndReviews"]

@st.cache_data
def load_data():
    return pd.DataFrame(list(collection.find()))
df = load_data()

def clean_price(x):
    if x is None:
        return None
    x = str(x).replace("$", "").replace(",", "").strip()
    try:
        return float(x)
    except:
        return None

df["price"] = df["price"].apply(clean_price)
df["bedrooms"] = pd.to_numeric(df["bedrooms"], errors="coerce").fillna(0)
df["rating"] = df["review_scores"].apply(lambda x: x.get("review_scores_rating") if isinstance(x, dict) else 0)
df["country"] = df["address"].apply(lambda x: x.get("country") if isinstance(x, dict) else "Unknown")
df["latitude"] = df["address"].apply(
    lambda x: x.get("location", {}).get("coordinates", [None, None])[1]
    if isinstance(x, dict) else None)
df["longitude"] = df["address"].apply(
    lambda x: x.get("location", {}).get("coordinates", [None, None])[0]
    if isinstance(x, dict) else None)
map_df = df.dropna(subset=["latitude", "longitude"])

st.header("Global Overview")
fig_map = px.scatter_geo(
    map_df,
    lat="latitude",
    lon="longitude",
    hover_name="name",
    hover_data={
        "price": True,
        "rating": True,
        "latitude": False,
        "longitude": False })

fig_map.update_traces(marker=dict(color="red",size=5,opacity=0.7))
fig_map.update_geos(
    projection_type="orthographic",
    showcountries=True,
    showland=True,
    landcolor="#eef5f5",
    oceancolor="#d9f1ff",
    showocean=True)

fig_map.update_layout(
    height=600,
    margin=dict(l=0, r=0, t=0, b=0),
    coloraxis_showscale=False )
st.plotly_chart(fig_map, use_container_width=True)
col1, col2, col3 = st.columns(3)
with col1:
    st.subheader("Top Countries")
    country_counts = df["country"].value_counts().head(10).reset_index()
    country_counts.columns = ["country", "count"]
    fig1 = px.bar(country_counts,x="country",y="count",text="count",color_discrete_sequence=["#a8dadc"])
    st.plotly_chart(fig1, use_container_width=True)

with col2:
    st.subheader("Property Type")
    prop = df["property_type"].value_counts().head(8).reset_index()
    prop.columns = ["property_type", "count"]
    pastel_colors = ["#a2d2ff","#bde0fe", "#cdb4db","#ffc8dd", "#ffafcc", "#b5ead7","#caffbf", "#ffd6a5"]
    fig2 = px.pie(prop,names="property_type",values="count",hole=0.5,color_discrete_sequence=pastel_colors)
    st.plotly_chart(fig2, use_container_width=True)

with col3:
    st.subheader("Average Rating")
    rating_df = df.groupby("country")["rating"].mean().sort_values(ascending=False).head(10).reset_index()
    fig3 = px.bar(rating_df,x="country",y="rating",text=rating_df["rating"].round(1),color_discrete_sequence=["#90e0ef"])
    st.plotly_chart(fig3, use_container_width=True)

st.sidebar.header("Filter")
countries = sorted(df["country"].unique())
selected_country = st.sidebar.multiselect("Country", options=countries)
if not selected_country:
    selected_country = countries

property_options = sorted(df["property_type"].unique())
selected_property = st.sidebar.multiselect("Property Type", options=property_options)
if not selected_property:
    selected_property = property_options

min_bedroom = st.sidebar.slider("Minimum Bedrooms", 0, 10, 3)
min_rating = st.sidebar.slider("Minimum Rating", 0, 100, 70)
sort_option = st.sidebar.selectbox("Sort Price", ["Low → High", "High → Low"])

filtered_df = df[
    (df["bedrooms"] >= min_bedroom) &
    (df["rating"] >= min_rating) &
    (df["property_type"].isin(selected_property)) &
    (df["country"].isin(selected_country))].copy()

price_asc = sort_option == "Low → High"
filtered_df = filtered_df.sort_values(by=["rating", "price"], ascending=[False, price_asc])

st.subheader(f"Results: {len(filtered_df)} listings")
if filtered_df.empty:
    st.error("No results found")
else:
    for _, row in filtered_df.iterrows():
        st.markdown("---")
        col1, col2 = st.columns([1.8, 1])

        with col1:
            st.subheader(row.get("name", "Unnamed Property"))
            st.write(row.get("summary", "No description available."))
            st.write(
                f"Price: ${row.get('price', 0):,.2f} | "
                f"Rating: {row.get('rating', 0)} | "
                f"Beds: {int(row.get('bedrooms', 0))}")

            btn1, btn2 = st.columns(2)
            with btn1:
                st.link_button("View Airbnb", row.get("listing_url", "#"), use_container_width=True)
            with btn2:
                coords = row.get("address", {}).get("location", {}).get("coordinates", [])
                if isinstance(coords, list) and len(coords) == 2:
                    st.link_button(
                        "Google Maps",
                        f"https://www.google.com/maps?q={coords[1]},{coords[0]}",
                        use_container_width=True)
        with col2:
            img_url = row.get("images", {}).get("picture_url")
            if img_url:
                st.image(img_url, use_container_width=True)
            else:
                st.write("No Image Available")
