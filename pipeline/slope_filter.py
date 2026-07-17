"""
pipeline/slope_filter.py
=========================
Stage 5 — Slope / Trajectory Filter

Validates the GPS flight trajectory within each segment.  A first-order
linear regression is fitted to the (longitude, latitude) point sequence;
images whose perpendicular residual exceeds ``slope_tolerance_percent``
of the regression slope are flagged as deviating from the expected
straight flight path.

This stage removes images taken during turns, aborted strip starts, or
GPS drift artefacts.

Author : Gudrun Kinz
License: MIT
"""

import logging
import numpy as np
import pandas as pd

from .config import PipelineConfig


class SlopeFilter:
    """
    Filter images whose GPS position deviates from the expected linear
    flight trajectory within each segment.

    Parameters
    ----------
    config : PipelineConfig
        Uses ``slope_tolerance_percent``.
    logger : logging.Logger
    """

    def __init__(self, config: PipelineConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger

    # ------------------------------------------------------------------
    def _filter_segment(self, seg_df: pd.DataFrame) -> pd.Index:
        """
        Return global index of rows to **remove** from one segment.

        At least 3 images are required to fit a line; segments with
        fewer images are skipped (all kept).
        """
        if len(seg_df) < 3:
            return pd.Index([])

        x = seg_df["longitude"].values
        y = seg_df["latitude"].values

        # Fit y = a*x + b
        coeffs = np.polyfit(x, y, 1)
        a = coeffs[0]

        y_pred    = np.polyval(coeffs, x)
        residuals = np.abs(y - y_pred)

        # Tolerance is a fraction of the slope magnitude
        tol = self.config.slope_tolerance_percent / 100.0 * np.abs(a)

        # Edge case: perfectly flat trajectory → use absolute tiny tolerance
        if tol == 0:
            tol = 1e-8

        out_local = residuals > tol
        return seg_df.index[out_local]

    # ------------------------------------------------------------------
    def filter(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply slope filter per flight segment.

        Only rows not already removed are evaluated.

        Parameters
        ----------
        df : pd.DataFrame
            Must contain ``latitude``, ``longitude``,
            ``flight_segment``, and ``stage`` columns.

        Returns
        -------
        pd.DataFrame
            Deviating rows tagged stage='removed',
            removal_reason='trajectory_deviation'.
        """
        self.logger.info("Stage 5 — Slope / Trajectory Filter")
        self.logger.info(
            f"  Tolerance: {self.config.slope_tolerance_percent}% "
            f"of regression slope"
        )

        active = df[df["stage"] != "removed"]
        all_out_idx = pd.Index([])

        for seg_id in active["flight_segment"].unique():
            seg_df  = active[active["flight_segment"] == seg_id]
            out_idx = self._filter_segment(seg_df)
            all_out_idx = all_out_idx.append(out_idx)
            if len(out_idx):
                self.logger.info(
                    f"  Segment {seg_id}: removed {len(out_idx)} "
                    f"trajectory-deviation images"
                )

        df.loc[all_out_idx, "stage"]          = "removed"
        df.loc[all_out_idx, "removal_reason"] = "trajectory_deviation"

        n_active  = len(active)
        n_removed = len(all_out_idx)
        n_kept    = n_active - n_removed

        self.logger.info(
            f"  Kept {n_kept}/{n_active} active images  "
            f"({100*n_kept/n_active:.1f}%)  —  "
            f"removed {n_removed} (trajectory deviation)"
        )

        return df

    # ------------------------------------------------------------------
    @staticmethod
    def summary(df: pd.DataFrame) -> dict:
        """Return a dict with per-segment removal counts."""
        removed = df[df["removal_reason"] == "trajectory_deviation"]
        return {
            "total_removed": len(removed),
            "by_segment": removed.groupby("flight_segment").size().to_dict(),
        }
