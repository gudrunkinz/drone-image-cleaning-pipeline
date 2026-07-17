"""
pipeline/flight_segmenter.py
=============================
Stage 2 — Flight Segmentation

Splits a chronologically sorted metadata table into distinct flight segments
based on temporal gaps between consecutive images.

Author : Gudrun Kinz
License: MIT
"""

import logging
import pandas as pd

from .config import PipelineConfig


class FlightSegmenter:
    """
    Assign a ``flight_segment`` integer label to every image row.

    Two consecutive images belong to the same segment when the time
    difference between them is less than ``config.flight_gap_minutes``.
    A gap equal to or larger than the threshold starts a new segment.

    Parameters
    ----------
    config : PipelineConfig
        Pipeline configuration (uses ``flight_gap_minutes``).
    logger : logging.Logger
        Logger instance shared across the pipeline.
    """

    def __init__(self, config: PipelineConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger

    # ------------------------------------------------------------------
    def segment_flights(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add a ``flight_segment`` column and a ``time_diff`` helper column.

        Parameters
        ----------
        df : pd.DataFrame
            Must contain a ``timestamp`` column (datetime).

        Returns
        -------
        pd.DataFrame
            Input DataFrame with two new columns:
            - ``time_diff``      : seconds since previous image (NaN for first row)
            - ``flight_segment`` : zero-based integer segment index
        """
        self.logger.info("Stage 2 — Flight Segmentation")

        df = df.sort_values("timestamp").reset_index(drop=True)

        # Time difference in minutes
        df["time_diff"] = (
            df["timestamp"].diff().dt.total_seconds() / 60.0
        )

        # New segment every time the gap exceeds the threshold
        df["flight_segment"] = (
            df["time_diff"] > self.config.flight_gap_minutes
        ).cumsum().astype(int)

        # Report
        counts = df["flight_segment"].value_counts().sort_index()
        self.logger.info(
            f"  Detected {len(counts)} flight segment(s):"
        )
        for seg_id, n in counts.items():
            start_ts = df.loc[df["flight_segment"] == seg_id, "timestamp"].iloc[0]
            end_ts   = df.loc[df["flight_segment"] == seg_id, "timestamp"].iloc[-1]
            self.logger.info(
                f"    Segment {seg_id:2d}: {n:4d} images  "
                f"[{start_ts.strftime('%H:%M:%S')} – {end_ts.strftime('%H:%M:%S')}]"
            )

        return df
