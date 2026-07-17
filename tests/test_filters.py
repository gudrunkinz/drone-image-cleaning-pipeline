"""
tests/test_filters.py
======================
Unit tests for the core pipeline filter modules.

Run with:
    pytest tests/

Author : Gudrun Kinz
License: MIT
"""

import logging
import pandas as pd
import numpy as np
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.config           import PipelineConfig
from pipeline.flight_segmenter import FlightSegmenter
from pipeline.yaw_filter       import YawFilter
from pipeline.altitude_filter  import AltitudeFilter
from pipeline.slope_filter     import SlopeFilter
from pipeline.grubbs_filter    import GrubbsFilter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def config():
    return PipelineConfig(
        flight_gap_minutes=10.0,
        yaw_threshold=200.0,
        min_altitude_m=235.0,
        max_altitude_m=250.0,
        slope_tolerance_percent=10.0,
        grubbs_alpha=0.05,
        grubbs_max_iterations=5,
    )


@pytest.fixture
def logger():
    return logging.getLogger("test_pipeline")


@pytest.fixture
def sample_df():
    """Small, realistic metadata DataFrame (10 images, 2 segments)."""
    from datetime import datetime, timedelta

    base = datetime(2022, 6, 1, 15, 0, 0)
    n    = 10
    rows = []
    for i in range(n):
        # Segment 0: images 0–4, segment 1: images 5–9 (gap > 10 min after img 4)
        if i < 5:
            ts = base + timedelta(seconds=5 * i)
        else:
            ts = base + timedelta(minutes=15, seconds=5 * (i - 5))

        rows.append({
            "Image_id":       f"IMG{i:04d}",
            "File Name":      f"IMG{i:04d}.IIQ",
            "timestamp":      ts,
            "latitude":       48.3192 + i * 0.00001,
            "longitude":      16.0676 + i * 0.00001,
            "altitude":       237.0 + np.random.uniform(-1, 1),
            "pitch":          -45.2 + np.random.uniform(-0.3, 0.3),
            "roll":           0.01 * i,
            "yaw":            72.0 + np.random.uniform(-3, 3),
            "flight_date":    "2022-06-01",
            "stage":          "kept",
            "removal_reason": "",
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# FlightSegmenter
# ---------------------------------------------------------------------------

class TestFlightSegmenter:

    def test_two_segments_detected(self, config, logger, sample_df):
        seg = FlightSegmenter(config, logger)
        df  = seg.segment_flights(sample_df)
        assert df["flight_segment"].nunique() == 2, "Expected 2 segments"

    def test_time_diff_column_created(self, config, logger, sample_df):
        seg = FlightSegmenter(config, logger)
        df  = seg.segment_flights(sample_df)
        assert "time_diff" in df.columns

    def test_first_row_timediff_nan(self, config, logger, sample_df):
        seg = FlightSegmenter(config, logger)
        df  = seg.segment_flights(sample_df)
        assert pd.isna(df["time_diff"].iloc[0])


# ---------------------------------------------------------------------------
# YawFilter
# ---------------------------------------------------------------------------

class TestYawFilter:

    def test_high_yaw_removed(self, config, logger, sample_df):
        # Inject one high-yaw image
        sample_df.loc[3, "yaw"] = 250.0
        seg = FlightSegmenter(config, logger)
        df  = seg.segment_flights(sample_df)

        yf = YawFilter(config, logger)
        df = yf.filter(df)

        assert df.loc[3, "stage"] == "removed"
        assert df.loc[3, "removal_reason"] == "other_direction"

    def test_low_yaw_kept(self, config, logger, sample_df):
        seg = FlightSegmenter(config, logger)
        df  = seg.segment_flights(sample_df)
        yf  = YawFilter(config, logger)
        df  = yf.filter(df)

        # All original yaw values are ~72°, well below 200°
        assert (df["stage"] == "kept").all()


# ---------------------------------------------------------------------------
# AltitudeFilter
# ---------------------------------------------------------------------------

class TestAltitudeFilter:

    def test_low_altitude_removed(self, config, logger, sample_df):
        sample_df.loc[2, "altitude"] = 220.0  # below 235 m
        seg = FlightSegmenter(config, logger)
        df  = seg.segment_flights(sample_df)
        af  = AltitudeFilter(config, logger)
        df  = af.filter(df)

        assert df.loc[2, "stage"] == "removed"
        assert df.loc[2, "removal_reason"] == "altitude_out_of_range"

    def test_in_range_kept(self, config, logger, sample_df):
        seg = FlightSegmenter(config, logger)
        df  = seg.segment_flights(sample_df)
        af  = AltitudeFilter(config, logger)
        df  = af.filter(df)

        # All altitudes are in 236–238 m
        assert (df["stage"] == "kept").all()

    def test_already_removed_not_relabelled(self, config, logger, sample_df):
        """Altitude filter must not overwrite an existing removal_reason."""
        sample_df.loc[1, "stage"]          = "removed"
        sample_df.loc[1, "removal_reason"] = "other_direction"
        sample_df.loc[1, "altitude"]       = 200.0  # also out of range

        seg = FlightSegmenter(config, logger)
        df  = seg.segment_flights(sample_df)
        af  = AltitudeFilter(config, logger)
        df  = af.filter(df)

        # Reason must remain 'other_direction', not be overwritten
        assert df.loc[1, "removal_reason"] == "other_direction"


# ---------------------------------------------------------------------------
# GrubbsFilter (statistical)
# ---------------------------------------------------------------------------

class TestGrubbsFilter:

    def test_extreme_outlier_removed(self, config, logger, sample_df):
        seg = FlightSegmenter(config, logger)
        df  = seg.segment_flights(sample_df)

        # Inject an obvious yaw outlier in segment 0
        df.loc[2, "yaw"] = 350.0  # far from cluster ~72°

        gf = GrubbsFilter(config, logger)
        df = gf.filter(df)

        assert df.loc[2, "stage"] == "removed"
        assert df.loc[2, "removal_reason"] == "grubbs_outlier"

    def test_uniform_data_no_removal(self, config, logger, sample_df):
        """Constant gimbal angles should produce zero Grubbs removals."""
        seg = FlightSegmenter(config, logger)
        df  = seg.segment_flights(sample_df)

        # Override angles to nearly identical values
        df["roll"]  = 0.0
        df["pitch"] = -45.0
        df["yaw"]   = 72.0

        gf = GrubbsFilter(config, logger)
        df = gf.filter(df)

        assert (df["stage"] == "kept").all()

