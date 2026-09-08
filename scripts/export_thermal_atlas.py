"""Build a small native-grid thermal-analysis packet from verified INCOIS inputs."""
import json
from pathlib import Path
import numpy as np
import xarray as xr
from backend.incois import load_incois

ROOT = Path(__file__).resolve().parents[1]


def export():
    model, _ = load_incois()  # Verifies original and converted source hashes.
    with xr.open_dataset(ROOT / 'data/incois/source.nc') as source:
        def values(name, index):
            data = source[name].isel(time=index).values.ravel()
            return [float(v) if np.isfinite(v) else None for v in data]
        packet = dict(
            schema='ocean3d-thermal-atlas-1',
            provenance=model.provenance,
            longitude=source.longitude.values.tolist(),
            latitude=source.latitude.values.tolist(),
            depth=source.ZAX.values.tolist(),
            frames=[dict(time=np.datetime_as_string(t, unit='s')+'Z',
                         temperature=values('T_ANALYZED', i),
                         local_count=values('T_BOXOBS', i),
                         influence_count=values('T_ROIOBS', i))
                    for i, t in enumerate(source.time.values)],
            method='Native INCOIS analyzed temperature, no spatial or temporal interpolation. '
                   'First downward threshold crossing from the shallowest native level; '
                   'continuous finite support and adjacent depth gaps <=150 m required. '
                   'A crossing interpolates only its two native depths. '
                   'Monthly differences are changes in analyzed isotherm depth, not tracked water motion.')
    path = ROOT / 'web/public/demo/incois-bob/thermal-structure.json'
    path.write_text(json.dumps(packet, separators=(',', ':'), allow_nan=False), encoding='utf-8')
    print(f'Thermal atlas: {len(packet["frames"])} frames, {len(packet["longitude"])*len(packet["latitude"])} native columns; {path.stat().st_size} bytes')


if __name__ == '__main__':
    export()
