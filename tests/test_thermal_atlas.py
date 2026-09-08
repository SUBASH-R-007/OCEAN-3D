"""Verify that the browser's thermal packet is an exact view of its source."""
import hashlib
import json
from pathlib import Path
import numpy as np
import xarray as xr

ROOT=Path(__file__).resolve().parents[1]


def test_native_thermal_packet_preserves_values_masks_counts_and_source_hash():
    packet=json.loads((ROOT/'web/public/demo/incois-bob/thermal-structure.json').read_text())
    path=ROOT/'data/incois/source.nc'
    assert packet['provenance']['source_sha256']==hashlib.sha256(path.read_bytes()).hexdigest()
    with xr.open_dataset(path) as source:
        for axis,native in [('depth','ZAX'),('longitude','longitude'),('latitude','latitude')]:
            np.testing.assert_array_equal(packet[axis],source[native].values)
        assert len(packet['frames'])==source.sizes['time']==3
        for i,frame in enumerate(packet['frames']):
            for target,original in [('temperature','T_ANALYZED'),('local_count','T_BOXOBS'),('influence_count','T_ROIOBS')]:
                np.testing.assert_allclose(np.array(frame[target],dtype=float),source[original].isel(time=i).values.ravel(),rtol=0,atol=0,equal_nan=True)


def test_relief_packet_is_georeferenced_and_linked_to_actual_raster():
    packet=json.loads((ROOT/'web/public/geography/bay-relief.json').read_text())
    assert packet['provenance']['sha256']==hashlib.sha256((ROOT/'data/geography/etopo-bay.tif').read_bytes()).hexdigest()
    assert len(packet['elevation'])==230*220
    np.testing.assert_allclose(packet['longitude'],76.05+np.arange(230)*.1)
    np.testing.assert_allclose(packet['latitude'],3.05+np.arange(220)*.1)
    values=np.array(packet['elevation'])
    assert np.isfinite(values).all() and values.min() < -4000 and values.max()>2000
    assert "ETOPO_2022_v1_15s_surface_elev" in packet['provenance']['source_url']
