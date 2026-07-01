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
        # Step 1: Read the secret variables from Google Cloud Run
        gee_key_string = os.environ.get("GEE_JSON_KEY")
        project_id = os.environ.get("GCP_PROJECT_ID")
        
        if not gee_key_string:
            gee_status = "Error: GEE_JSON_KEY environment variable is missing"
        else:
            # Step 2: Pass the raw string directly to Earth Engine
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

# Allow your Netlify frontend to communicate with this backend securely
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"],
)

# Diagnostic homepage (What you see when you visit the Cloud Run URL directly)
@app.get("/")
def health_check():
    return {
        "server_status": "Server is running perfectly!", 
        "earth_engine_status": gee_status
    }

# The endpoint your mobile app talks to
@app.get("/api/map-tiles")
def get_map_tiles(product: str = 'POP', epoch: str = '2020'):
    if gee_status != "Success":
        return {"error": gee_status}
    
    try:
        # 1. Select the Dataset and the matching Color Palette
        if product == 'POP':
            # Population Density (Black -> Blue -> Cyan -> Green -> Yellow -> Red)
            dataset = ee.ImageCollection("JRC/GHSL/P2023A/GHS_POP")
            vis_params = {'min': 0.0, 'max': 100.0, 'palette': ['000004', '3b0f70', '8c2981', 'de4968', 'fe9f6d', 'fcfdbf']}
            
        elif product == 'BUILT_S':
            # Built-Up Surface / Concrete (Black -> White)
            dataset = ee.ImageCollection("JRC/GHSL/P2023A/GHS_BUILT_S")
            vis_params = {'min': 0.0, 'max': 100.0, 'palette': ['000000', '444444', '999999', 'FFFFFF']}
            
        elif product == 'BUILT_V':
            # Building Volume / 3D Height Proxy (Black -> Dark Green -> Light Green)
            dataset = ee.ImageCollection("JRC/GHSL/P2023A/GHS_BUILT_V")
            vis_params = {'min': 0.0, 'max': 50.0, 'palette': ['000000', '004400', '00AA00', '00FF00']}
            
        elif product == 'SMOD':
            # Settlement Model / Degree of Urbanization (Categorical Classes)
            dataset = ee.ImageCollection("JRC/GHSL/P2023A/GHS_SMOD")
            # 10=Water, 11=Very Rural, 21=Suburban, 30=Urban Center
            vis_params = {'min': 10.0, 'max': 30.0, 'palette': ['0000AA', '004400', 'FFFF00', 'FF0000']}
            
        else:
            return {"error": "Invalid product selected"}

        # 2. Filter by the specific year (Epoch) requested by the frontend
        start_date = f"{epoch}-01-01"
        end_date = f"{epoch}-12-31"
        
        # We use .first() because GHSL releases one global mosaic per year
        image = dataset.filterDate(start_date, end_date).first()

        # 3. Request the temporary map tile URL from Google
        map_id_dict = ee.Image(image).getMapId(vis_params)
        
        return {"tile_url": map_id_dict['tile_fetcher'].url_format}
        
    except Exception as e:
        return {"error": str(e)}