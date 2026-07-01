import os
import json
import ee
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# We create a variable to track if Earth Engine logged in successfully
gee_status = "Not Initialized"

@asynccontextmanager
async def lifespan(app: FastAPI):
    global gee_status
    try:
        # Step 1: Try to read the secret variables
        gee_key_string = os.environ.get("GEE_JSON_KEY")
        project_id = os.environ.get("GCP_PROJECT_ID")
        
        if not gee_key_string:
            gee_status = "Error: GEE_JSON_KEY environment variable is missing"
        else:
            # Step 2: Try to log in
            key_dict = json.loads(gee_key_string)
            auth = ee.ServiceAccountCredentials(None, key_data=key_dict)
            ee.Initialize(credentials=auth, project=project_id)
            gee_status = "Success"
            print("Earth Engine Initialized Successfully!")
            
    except Exception as e:
        # If the JSON is copied wrong, it will catch the error here!
        gee_status = f"Failed to initialize Earth Engine: {str(e)}"
        print(gee_status)
    yield

# Start FastAPI with our safe lifespan function
app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"],
)

# A new homepage just for you to check the status!
@app.get("/")
def health_check():
    return {
        "server_status": "Server is running perfectly!", 
        "earth_engine_status": gee_status
    }

@app.get("/api/map-tiles")
def get_map_tiles():
    if gee_status != "Success":
        return {"error": gee_status}
    
    try:
        image = ee.Image('USGS/SRTMGL1_003')
        vis_params = {'min': 0, 'max': 3000, 'palette': ['blue', 'green', 'red']}
        map_id_dict = ee.Image(image).getMapId(vis_params)
        return {"tile_url": map_id_dict['tile_fetcher'].url_format}
    except Exception as e:
        return {"error": str(e)}