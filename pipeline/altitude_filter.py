"""
pipeline/altitude_filter.py
============================
Stage 4 — Altitude Filter

Removes images acquired outside the nominal survey altitude range.
Altitude is taken directly from the GPS altitude field in the IIQ EXIF
metadata (metres, WGS-84 ellipsoidal height).

For the BOKU Tulln field site the nominal survey altitude was 40 m AGL
above a terrain elevation of ~195 m, giving an absolute GPS altitude of
~235 m.  A ±15 m window (235–250 m) is used as default.

Author : Gudrun Kinz
License: MIT
"""

import logging
import pandas as pd

from .config import PipelineConfig


class AltitudeFilter:
    """
    Filter images by GPS altitude.

    Parameters
    ----------
    config : PipelineConfig
        Uses ``min_altitude_m`` and ``max_altitude_m``.
    logger : logging.Logger
    """

    def __init__(self, config: PipelineConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger

    # ------------------------------------------------------------------
    def filter(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Flag images outside [min_altitude_m, max_altitude_m] as removed.

        Only rows whose ``stage`` is currently *not* already 'removed'
        are evaluated, so this filter is safely stackable after yaw
        filtering.

        Parameters
        ----------
        df : pd.DataFrame
            Must contain an ``altitude`` column (metres).

        Returns
        -------
        pd.DataFrame
            Rows outside the altitude window are tagged
            stage='removed', removal_reason='altitude_out_of_range'.
        """
        self.logger.info("Stage 4 — Altitude Filter")
        self.logger.info(
            f"  Window: [{self.config.min_altitude_m}, "
            f"{self.config.max_altitude_m}] m"
        )

        # Only test images not already removed
        candidate_mask = df["stage"] != "removed"
        candidates = df[candidate_mask]

        in_range = (
            (candidates["altitude"] >= self.config.min_altitude_m) &
            (candidates["altitude"] <= self.config.max_altitude_m)
        )

        # Global indices of out-of-range images
        out_idx = candidates.index[~in_range]

        df.loc[out_idx, "stage"]          = "removed"
        df.loc[out_idx, "removal_reason"] = "altitude_out_of_range"

        n_active  = candidate_mask.sum()
        n_removed = len(out_idx)
        n_kept    = n_active - n_removed

        self.logger.info(
            f"  Kept {n_kept}/{n_active} active images  "
            f"({100*n_kept/n_active:.1f}%)  —  "
            f"removed {n_removed} (altitude out of range)"
        )

        return df

    # ------------------------------------------------------------------
    @staticmethod
    def summary(df: pd.DataFrame) -> dict:
        """Return a dict with per-segment removal counts."""
        removed = df[df["removal_reason"] == "altitude_out_of_range"]
        return {
            "total_removed": len(removed),
            "by_segment": removed.groupby("flight_segment").size().to_dict(),
        }
