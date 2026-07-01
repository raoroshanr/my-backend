import os
import json
import ee
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# We will put your Netlify URL here in Phase 4!
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"],
)

# Login to Google Earth Engine securely
gee_key_string = os.environ.get("GEE_JSON_KEY")
if gee_key_string:
    auth = ee.ServiceAccountCredentials(None, key_data=json.loads(gee_key_string))
    ee.Initialize(credentials=auth, project=os.environ.get("GCP_PROJECT_ID"))

@app.get("/api/map-tiles")
def get_map_tiles():
    try:
        # Get a basic elevation map for testing
        image = ee.Image('USGS/SRTMGL1_003')
        vis_params = {'min': 0, 'max': 3000, 'palette': ['blue', 'green', 'red']}
        
        # Generate the map layer
        map_id_dict = ee.Image(image).getMapId(vis_params)
        return {"tile_url": map_id_dict['tile_fetcher'].url_format}
    except Exception as e:
        return {"error": str(e)}