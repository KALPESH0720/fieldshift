path = 'src/fieldshift/engine/recommend.py'
with open(path) as f:
    text = f.read()

target1 = 'features = self.store.get_cell_features(cell.cell_id)\n'
replacement1 = 'features = self.store.get_cell_features(cell.cell_id)\n        if features is None:\n            features = self._fetch_cell_on_demand(cell)\n'

target2 = '    @staticmethod\n    def _prices'
replacement2 = '''    def _fetch_cell_on_demand(self, cell):
        try:
            from datetime import date
            from ..common.region import RegionConfig
            from ..data.power import PowerClient
            from ..data.soilgrids import SyntheticSoilProvider
            from ..features.layer_build import CellInputs, build_cell_features

            start = date(2015, 1, 1)
            end = date(2025, 3, 31)
            client = PowerClient()
            weather = client.fetch(cell.cell_id, cell.center_lat, cell.center_lon, start, end)

            min_lon = round(cell.center_lon - cell.size_deg / 2, 6)
            min_lat = round(cell.center_lat - cell.size_deg / 2, 6)
            max_lon = round(cell.center_lon + cell.size_deg / 2, 6)
            max_lat = round(cell.center_lat + cell.size_deg / 2, 6)

            region = RegionConfig.model_validate({
                "id": "on_demand",
                "name": f"Cell {cell.cell_id}",
                "status": "active",
                "bbox": [min_lon, min_lat, max_lon, max_lat],
                "cell_size_deg": cell.size_deg,
                "climate_years": [2015, 2024],
                "crops": [],
                "seasons": {
                    "kharif": {"start": [6, 1], "end": [10, 31]},
                    "rabi": {"start": [11, 1], "end": [3, 31]},
                },
            })
            soil_point = SyntheticSoilProvider().sample(cell)
            inp = CellInputs(weather=weather, soil=soil_point, synthetic=False)
            feat, _ = build_cell_features(cell, region, inp, "nasa_power_live")
            self.store.put_cell_features(feat)
            log.info("Successfully fetched on-demand NASA POWER features for cell %s (%s, %s)",
                     cell.cell_id, cell.center_lat, cell.center_lon)
            return feat
        except Exception as e:
            log.warning("On-demand NASA fetch for cell %s failed: %s", cell.cell_id, e)
            return None

    @staticmethod
    def _prices'''

if target1 in text and '_fetch_cell_on_demand' not in text:
    text = text.replace(target1, replacement1, 1)
if target2 in text and 'def _fetch_cell_on_demand' not in text:
    text = text.replace(target2, replacement2, 1)

with open(path, 'w') as f:
    f.write(text)

print("Patch applied successfully! Has function:", "_fetch_cell_on_demand" in text)

