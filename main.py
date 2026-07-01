@app.get("/api/map-tiles")
def get_map_tiles(product: str = 'POP', epoch: str = '2020', region: str = 'All'):
    if gee_status != "Success":
        return {"error": gee_status}
    
    try:
        # --- SMART ROUTER ---
        # 1. Standard Time-Series Datasets
        if product in ['POP', 'BUILT_S', 'BUILT_V', 'SMOD']:
            
            if product == 'POP':
                dataset = ee.ImageCollection("JRC/GHSL/P2023A/GHS_POP")
                vis_params = {'min': 0.0, 'max': 100.0, 'palette': ['000004', '3b0f70', '8c2981', 'de4968', 'fe9f6d', 'fcfdbf']}
            elif product == 'BUILT_S':
                dataset = ee.ImageCollection("JRC/GHSL/P2023A/GHS_BUILT_S")
                vis_params = {'min': 0.0, 'max': 100.0, 'palette': ['000000', '444444', '999999', 'FFFFFF']}
            elif product == 'BUILT_V':
                dataset = ee.ImageCollection("JRC/GHSL/P2023A/GHS_BUILT_V")
                vis_params = {'min': 0.0, 'max': 50.0, 'palette': ['000000', '004400', '00AA00', '00FF00']}
            elif product == 'SMOD':
                dataset = ee.ImageCollection("JRC/GHSL/P2023A/GHS_SMOD")
                vis_params = {'min': 10.0, 'max': 30.0, 'palette': ['0000AA', '004400', 'FFFF00', 'FF0000']}

            # Filter Collection by Year
            start_date = f"{epoch}-01-01"
            end_date = f"{epoch}-12-31"
            image = dataset.filterDate(start_date, end_date).first()

        # 2. Single-Snapshot Datasets (e.g., 2018 Building Heights)
        elif product == 'BUILT_H':
            # Note: We load this directly as a single Image, no date filtering required!
            image = ee.Image("JRC/GHSL/P2023A/GHS_BUILT_H/2018")
            vis_params = {'min': 0.0, 'max': 30.0, 'palette': ['000000', '0000FF', 'FF0000', 'FFFF00']}

        # 3. Massive Vector Datasets (e.g., OBAT Building Footprints)
        elif product == 'OBAT':
            # Load from the community catalog (Vector FeatureCollection)
            vector_data = ee.FeatureCollection("projects/sat-io/open-datasets/ghs-obat")
            
            # Server-Side Rasterization: We tell Google to paint the polygons into pixels!
            # We color them solid cyan with a dark blue outline
            image = vector_data.style(**{
                'color': '000055',
                'width': 1,
                'fillColor': '00FFFF'
            })
            # Style() returns an RGB image, so we don't need min/max/palette vis_params
            vis_params = {}

        else:
            return {"error": "Invalid product selected"}

        # --- BOUNDARY CLIPPING ---
        if region != 'All':
            boundaries = ee.FeatureCollection("FAO/GAUL/2015/level2")
            selected_boundary = boundaries.filter(ee.Filter.eq('ADM2_NAME', region))
            image = image.clipToCollection(selected_boundary)

        # --- FETCH URL ---
        map_id_dict = ee.Image(image).getMapId(vis_params)
        return {"tile_url": map_id_dict['tile_fetcher'].url_format}
        
    except Exception as e:
        return {"error": str(e)}