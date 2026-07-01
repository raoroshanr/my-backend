import os
import ee
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# Track if Earth Engine logged in successfully
gee_status = "Not Initialized"

@asynccontextmanager
async def lifespan(app: FastAPI):
    global gee_status
    try:
        # Step 1: Read the secret variables from Google Cloud
        gee_key_string = os.environ.get("GEE_JSON_KEY")
        project_id = os.environ.get("GCP_PROJECT_ID")
        
        if not gee_key_string:
            gee_status = "Error: GEE_JSON_KEY environment variable is missing"
        else:
            # Step 2: Pass the raw string directly to Earth Engine (No json.loads needed!)
            auth = ee.ServiceAccountCredentials(None, key_data=gee_key_string)
            ee.Initialize(credentials=auth, project=project_id)
            
            gee_status = "Success"
            print("Earth Engine Initialized Successfully!")
            
    except Exception as e:
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

# Your diagnostic homepage
@app.get("/")
def health_check():
    return {
        "server_status": "Server is running perfectly!", 
        "earth_engine_status": gee_status
    }

# The endpoint Netlify will talk to
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