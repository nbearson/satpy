#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2017-2018 Satpy developers
#
# This file is part of satpy.
#
# satpy is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# satpy is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# satpy.  If not, see <http://www.gnu.org/licenses/>.
"""Tests for the SCMI writer."""
import os
from glob import glob
from datetime import datetime, timedelta

import numpy as np
import dask.array as da

import unittest


def check_required_common_attributes(ds):
    """Check common properties of the created AWIPS tiles for validity."""
    assert 'x' in ds.coords
    x_coord = ds.coords['x']
    np.testing.assert_equal(np.diff(x_coord), 1)
    x_attrs = x_coord.attrs
    assert x_attrs.get('standard_name') == 'projection_x_coordinate'
    assert x_attrs.get('units') == 'meters'
    assert 'scale_factor' in x_attrs
    assert 'add_offset' in x_attrs

    assert 'y' in ds.coords
    y_coord = ds.coords['y']
    np.testing.assert_equal(np.diff(y_coord), 1)
    y_attrs = y_coord.attrs
    assert y_attrs.get('standard_name') == 'projection_y_coordinate'
    assert y_attrs.get('units') == 'meters'
    assert 'scale_factor' in y_attrs
    assert 'add_offset' in y_attrs

    for attr_name in ('tile_row_offset', 'tile_column_offset',
                      'product_tile_height', 'product_tile_width',
                      'number_product_tiles',
                      'product_rows', 'product_columns'):
        assert attr_name in ds.attrs

    for data_arr in ds.data_vars.values():
        if data_arr.ndim == 0:
            # grid mapping variable
            assert 'grid_mapping_name' in data_arr.attrs
            continue
        assert 'grid_mapping' in data_arr.attrs
        assert data_arr.attrs['grid_mapping'] in ds


class TestSCMIWriter(unittest.TestCase):
    """Test basic functionality of SCMI writer."""

    def setUp(self):
        """Create temporary directory to save files to."""
        import tempfile
        self.base_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Remove the temporary directory created for a test."""
        try:
            import shutil
            shutil.rmtree(self.base_dir, ignore_errors=True)
        except OSError:
            pass

    def test_init(self):
        """Test basic init method of writer."""
        from satpy.writers.scmi import SCMIWriter
        SCMIWriter(base_dir=self.base_dir)

    def test_basic_numbered_1_tile(self):
        """Test creating a single numbered tile."""
        from satpy.writers.scmi import SCMIWriter
        import xarray as xr
        from xarray import DataArray
        from pyresample.geometry import AreaDefinition
        from pyresample.utils import proj4_str_to_dict
        w = SCMIWriter(base_dir=self.base_dir, compress=True)
        area_def = AreaDefinition(
            'test',
            'test',
            'test',
            proj4_str_to_dict('+proj=lcc +datum=WGS84 +ellps=WGS84 +lon_0=-95. '
                              '+lat_0=25 +lat_1=25 +units=m +no_defs'),
            100,
            200,
            (-1000., -1500., 1000., 1500.),
        )
        now = datetime(2018, 1, 1, 12, 0, 0)
        data = np.linspace(0., 1., 20000, dtype=np.float32).reshape((200, 100))
        ds = DataArray(
            da.from_array(data, chunks=50),
            attrs=dict(
                name='test_ds',
                platform_name='PLAT',
                sensor='SENSOR',
                units='1',
                area=area_def,
                start_time=now,
                end_time=now + timedelta(minutes=20))
        )
        w.save_datasets([ds], sector_id='TEST', source_name='TESTS')
        all_files = glob(os.path.join(self.base_dir, 'TESTS_AII*.nc'))
        self.assertEqual(len(all_files), 1)
        self.assertEqual(os.path.basename(all_files[0]), 'TESTS_AII_PLAT_SENSOR_test_ds_TEST_T001_20180101_1200.nc')
        for fn in all_files:
            ds = xr.open_dataset(fn, mask_and_scale=False)
            check_required_common_attributes(ds)
            ds = xr.open_dataset(fn, mask_and_scale=True)
            np.testing.assert_allclose(data, ds['data'].data, rtol=0.1)

    def test_basic_numbered_tiles(self):
        """Test creating a multiple numbered tiles."""
        import xarray as xr
        from satpy.writers.scmi import SCMIWriter
        from xarray import DataArray
        from pyresample.geometry import AreaDefinition
        from pyresample.utils import proj4_str_to_dict
        w = SCMIWriter(base_dir=self.base_dir, compress=True)
        area_def = AreaDefinition(
            'test',
            'test',
            'test',
            proj4_str_to_dict('+proj=lcc +datum=WGS84 +ellps=WGS84 +lon_0=-95. '
                              '+lat_0=25 +lat_1=25 +units=m +no_defs'),
            100,
            200,
            (-1000., -1500., 1000., 1500.),
        )
        now = datetime(2018, 1, 1, 12, 0, 0)
        ds = DataArray(
            da.from_array(np.linspace(0., 1., 20000, dtype=np.float32).reshape((200, 100)), chunks=50),
            attrs=dict(
                name='test_ds',
                platform_name='PLAT',
                sensor='SENSOR',
                units='1',
                area=area_def,
                start_time=now,
                end_time=now + timedelta(minutes=20))
        )
        w.save_datasets([ds], sector_id='TEST', source_name="TESTS", tile_count=(3, 3))
        all_files = glob(os.path.join(self.base_dir, 'TESTS_AII*.nc'))
        self.assertEqual(len(all_files), 9)
        for fn in all_files:
            ds = xr.open_dataset(fn, mask_and_scale=False)
            check_required_common_attributes(ds)
            assert ds.attrs['start_date_time'] == now.strftime('%Y-%m-%dT%H:%M:%S')

    def test_basic_lettered_tiles(self):
        """Test creating a lettered grid."""
        import xarray as xr
        from satpy.writers.scmi import SCMIWriter
        from xarray import DataArray
        from pyresample.geometry import AreaDefinition
        from pyresample.utils import proj4_str_to_dict
        w = SCMIWriter(base_dir=self.base_dir, compress=True)
        area_def = AreaDefinition(
            'test',
            'test',
            'test',
            proj4_str_to_dict('+proj=lcc +datum=WGS84 +ellps=WGS84 +lon_0=-95. '
                              '+lat_0=25 +lat_1=25 +units=m +no_defs'),
            1000,
            2000,
            (-1000000., -1500000., 1000000., 1500000.),
        )
        now = datetime(2018, 1, 1, 12, 0, 0)
        ds = DataArray(
            da.from_array(np.linspace(0., 1., 2000000, dtype=np.float32).reshape((2000, 1000)), chunks=500),
            attrs=dict(
                name='test_ds',
                platform_name='PLAT',
                sensor='SENSOR',
                units='1',
                area=area_def,
                start_time=now,
                end_time=now + timedelta(minutes=20))
        )
        # tile_count should be ignored since we specified lettered_grid
        w.save_datasets([ds], sector_id='LCC', source_name="TESTS", tile_count=(3, 3), lettered_grid=True)
        all_files = glob(os.path.join(self.base_dir, 'TESTS_AII*.nc'))
        self.assertEqual(len(all_files), 16)
        for fn in all_files:
            ds = xr.open_dataset(fn, mask_and_scale=False)
            check_required_common_attributes(ds)
            assert ds.attrs['start_date_time'] == now.strftime('%Y-%m-%dT%H:%M:%S')

    def test_lettered_tiles_sector_ref(self):
        """Test creating a lettered grid using the sector as reference."""
        import xarray as xr
        from satpy.writers.scmi import SCMIWriter
        from xarray import DataArray
        from pyresample.geometry import AreaDefinition
        from pyresample.utils import proj4_str_to_dict
        w = SCMIWriter(base_dir=self.base_dir, compress=True)
        area_def = AreaDefinition(
            'test',
            'test',
            'test',
            proj4_str_to_dict('+proj=lcc +datum=WGS84 +ellps=WGS84 +lon_0=-95. '
                              '+lat_0=25 +lat_1=25 +units=m +no_defs'),
            1000,
            2000,
            (-1000000., -1500000., 1000000., 1500000.),
        )
        now = datetime(2018, 1, 1, 12, 0, 0)
        ds = DataArray(
            da.from_array(np.linspace(0., 1., 2000000, dtype=np.float32).reshape((2000, 1000)), chunks=500),
            attrs=dict(
                name='test_ds',
                platform_name='PLAT',
                sensor='SENSOR',
                units='1',
                area=area_def,
                start_time=now,
                end_time=now + timedelta(minutes=20))
        )
        w.save_datasets([ds], sector_id='LCC', source_name="TESTS",
                        lettered_grid=True, use_sector_reference=True,
                        use_end_time=True)
        all_files = glob(os.path.join(self.base_dir, 'TESTS_AII*.nc'))
        self.assertEqual(len(all_files), 16)
        for fn in all_files:
            ds = xr.open_dataset(fn, mask_and_scale=False)
            check_required_common_attributes(ds)
            assert ds.attrs['start_date_time'] == (now + timedelta(minutes=20)).strftime('%Y-%m-%dT%H:%M:%S')

    def test_lettered_tiles_no_fit(self):
        """Test creating a lettered grid with no data overlapping the grid."""
        from satpy.writers.scmi import SCMIWriter
        from xarray import DataArray
        from pyresample.geometry import AreaDefinition
        from pyresample.utils import proj4_str_to_dict
        w = SCMIWriter(base_dir=self.base_dir, compress=True)
        area_def = AreaDefinition(
            'test',
            'test',
            'test',
            proj4_str_to_dict('+proj=lcc +datum=WGS84 +ellps=WGS84 +lon_0=-95. '
                              '+lat_0=25 +lat_1=25 +units=m +no_defs'),
            1000,
            2000,
            (4000000., 5000000., 5000000., 6000000.),
        )
        now = datetime(2018, 1, 1, 12, 0, 0)
        ds = DataArray(
            da.from_array(np.linspace(0., 1., 2000000, dtype=np.float32).reshape((2000, 1000)), chunks=500),
            attrs=dict(
                name='test_ds',
                platform_name='PLAT',
                sensor='SENSOR',
                units='1',
                area=area_def,
                start_time=now,
                end_time=now + timedelta(minutes=20))
        )
        w.save_datasets([ds], sector_id='LCC', source_name="TESTS", tile_count=(3, 3), lettered_grid=True)
        # No files created
        all_files = glob(os.path.join(self.base_dir, 'TESTS_AII*.nc'))
        self.assertEqual(len(all_files), 0)

    def test_lettered_tiles_no_valid_data(self):
        """Test creating a lettered grid with no valid data."""
        from satpy.writers.scmi import SCMIWriter
        from xarray import DataArray
        from pyresample.geometry import AreaDefinition
        from pyresample.utils import proj4_str_to_dict
        w = SCMIWriter(base_dir=self.base_dir, compress=True)
        area_def = AreaDefinition(
            'test',
            'test',
            'test',
            proj4_str_to_dict('+proj=lcc +datum=WGS84 +ellps=WGS84 +lon_0=-95. '
                              '+lat_0=25 +lat_1=25 +units=m +no_defs'),
            1000,
            2000,
            (-1000000., -1500000., 1000000., 1500000.),
        )
        now = datetime(2018, 1, 1, 12, 0, 0)
        ds = DataArray(
            da.full((2000, 1000), np.nan, chunks=500, dtype=np.float32),
            attrs=dict(
                name='test_ds',
                platform_name='PLAT',
                sensor='SENSOR',
                units='1',
                area=area_def,
                start_time=now,
                end_time=now + timedelta(minutes=20))
        )
        w.save_datasets([ds], sector_id='LCC', source_name="TESTS", tile_count=(3, 3), lettered_grid=True)
        # No files created - all NaNs should result in no tiles being created
        all_files = glob(os.path.join(self.base_dir, 'TESTS_AII*.nc'))
        self.assertEqual(len(all_files), 0)

    def test_lettered_tiles_bad_filename(self):
        """Test creating a lettered grid with a bad filename."""
        from satpy.writers.scmi import SCMIWriter
        from xarray import DataArray
        from pyresample.geometry import AreaDefinition
        from pyresample.utils import proj4_str_to_dict
        w = SCMIWriter(base_dir=self.base_dir, compress=True, filename="{Bad Key}.nc")
        area_def = AreaDefinition(
            'test',
            'test',
            'test',
            proj4_str_to_dict('+proj=lcc +datum=WGS84 +ellps=WGS84 +lon_0=-95. '
                              '+lat_0=25 +lat_1=25 +units=m +no_defs'),
            1000,
            2000,
            (-1000000., -1500000., 1000000., 1500000.),
        )
        now = datetime(2018, 1, 1, 12, 0, 0)
        ds = DataArray(
            da.from_array(np.linspace(0., 1., 2000000, dtype=np.float32).reshape((2000, 1000)), chunks=500),
            attrs=dict(
                name='test_ds',
                platform_name='PLAT',
                sensor='SENSOR',
                units='1',
                area=area_def,
                start_time=now,
                end_time=now + timedelta(minutes=20))
        )
        self.assertRaises(KeyError, w.save_datasets,
                          [ds],
                          sector_id='LCC',
                          source_name='TESTS',
                          tile_count=(3, 3),
                          lettered_grid=True)

    def test_basic_numbered_tiles_rgb(self):
        """Test creating a multiple numbered tiles with RGB."""
        from satpy.writers.scmi import SCMIWriter
        import xarray as xr
        from xarray import DataArray
        from pyresample.geometry import AreaDefinition
        from pyresample.utils import proj4_str_to_dict
        w = SCMIWriter(base_dir=self.base_dir, compress=True)
        area_def = AreaDefinition(
            'test',
            'test',
            'test',
            proj4_str_to_dict('+proj=lcc +datum=WGS84 +ellps=WGS84 +lon_0=-95. '
                              '+lat_0=25 +lat_1=25 +units=m +no_defs'),
            100,
            200,
            (-1000., -1500., 1000., 1500.),
        )
        now = datetime(2018, 1, 1, 12, 0, 0)
        ds = DataArray(
            da.from_array(np.linspace(0., 1., 60000, dtype=np.float32).reshape((3, 200, 100)), chunks=50),
            dims=('bands', 'y', 'x'),
            coords={'bands': ['R', 'G', 'B']},
            attrs=dict(
                name='test_ds',
                platform_name='PLAT',
                sensor='SENSOR',
                units='1',
                area=area_def,
                start_time=now,
                end_time=now + timedelta(minutes=20))
        )
        w.save_datasets([ds], sector_id='TEST', source_name="TESTS", tile_count=(3, 3))
        chan_files = glob(os.path.join(self.base_dir, 'TESTS_AII*test_ds_R*.nc'))
        all_files = chan_files[:]
        self.assertEqual(len(chan_files), 9)
        chan_files = glob(os.path.join(self.base_dir, 'TESTS_AII*test_ds_G*.nc'))
        all_files.extend(chan_files)
        self.assertEqual(len(chan_files), 9)
        chan_files = glob(os.path.join(self.base_dir, 'TESTS_AII*test_ds_B*.nc'))
        self.assertEqual(len(chan_files), 9)
        all_files.extend(chan_files)
        for fn in all_files:
            ds = xr.open_dataset(fn, mask_and_scale=False)
            check_required_common_attributes(ds)
