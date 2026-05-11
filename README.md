# Mini Airbnb Dashboard

Streamlit dashboard for exploring Airbnb listings from MongoDB.

## Run locally

1. Create `.streamlit/secrets.toml`
2. Add your MongoDB connection string:

```toml
MONGODB_URI = "your-mongodb-uri"
```

3. Install dependencies and start the app:

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy

Deploy on Streamlit Community Cloud and set `MONGODB_URI` in app secrets.
