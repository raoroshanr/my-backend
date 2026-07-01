@app.get("/api/map-tiles")
def get_map_tiles(product: str = 'POP', epoch: str = '2020'):
    if gee_status != "Success":
        return {"error": gee_status}
    
    try:
        # 1. Select the correct GHSL Dataset based on the dropdown
        if product == 'POP':
            # Global Population Density
            dataset = ee.ImageCollection("JRC/GHSL/P2023A/GHS_POP")
            # Black to Blue to Red heatmap
            vis_params = {'min': 0.0, 'max': 100.0, 'palette': ['000000', '0000FF', '00FFFF', '00FF00', 'FFFF00', 'FF0000']}
        
        elif product == 'BUILT_S':
            # Built-Up Surface Area (Buildings/Concrete)
            dataset = ee.ImageCollection("JRC/GHSL/P2023A/GHS_BUILT_S")
            # Black to White grayscale
            vis_params = {'min': 0.0, 'max': 100.0, 'palette': ['000000', '333333', '999999', 'FFFFFF']}
            
        else:
            return {"error": "Invalid product selected"}

        # 2. Filter the dataset to find the exact epoch (year) requested
        # We look for any image published within that specific year
        start_date = f"{epoch}-01-01"
        end_date = f"{epoch}-12-31"
        image = dataset.filterDate(start_date, end_date).first()

        # 3. Generate the map tile URL
        map_id_dict = ee.Image(image).getMapId(vis_params)
        
        return {"tile_url": map_id_dict['tile_fetcher'].url_format}
        
    except Exception as e:
        return {"error": str(e)}