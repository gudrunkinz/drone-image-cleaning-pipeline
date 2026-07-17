"""
pipeline/yaw_filter.py
=======================
Stage 3 — Yaw / Flight-Direction Filter

Retains only images recorded while the UAV was flying in the desired
direction (south → north for the BOKU Tulln wheat experiments).  Images
captured on return transects (yaw ≥ threshold) are flagged as removed.

The threshold of 200° was determined empirically from the yaw histogram
of the Phase One IIQ metadata: south-to-north flights cluster around
~72° and north-to-south flights cluster around ~252°, giving a clean
separation at 200°.

Author : Gudrun Kinz
License: MIT
"""

import logging
import pandas as pd

from .config import PipelineConfig


class YawFilter:
    """
    Filter images by gimbal yaw angle.

    Parameters
    ----------
    config : PipelineConfig
        Uses ``yaw_threshold`` (default 200°).
    logger : logging.Logger
    """

    def __init__(self, config: PipelineConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger

    # ------------------------------------------------------------------
    def filter(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply yaw filter and annotate the ``stage`` / ``removal_reason``
        columns in place.

        Parameters
        ----------
        df : pd.DataFrame
            Must contain a ``yaw`` column (degrees, 0–360).

        Returns
        -------
        pd.DataFrame
            Rows with ``yaw < yaw_threshold`` are kept;
            the rest are tagged  stage='removed', removal_reason='other_direction'.
        """
        self.logger.info("Stage 3 — Yaw Filter")
        self.logger.info(f"  Threshold: yaw < {self.config.yaw_threshold}°  "
                         f"(target: south → north)")

        kept_mask = df["yaw"] < self.config.yaw_threshold

        # Annotate removed rows
        df.loc[~kept_mask, "stage"]          = "removed"
        df.loc[~kept_mask, "removal_reason"] = "other_direction"

        n_total   = len(df)
        n_kept    = kept_mask.sum()
        n_removed = n_total - n_kept

        self.logger.info(
            f"  Kept {n_kept}/{n_total}  "
            f"({100*n_kept/n_total:.1f}%)  —  "
            f"removed {n_removed} (wrong direction)"
        )

        return df

    # ------------------------------------------------------------------
    @staticmethod
    def summary(df: pd.DataFrame) -> dict:
        """Return a dict with per-segment removal counts."""
        removed = df[df["removal_reason"] == "other_direction"]
        return {
            "total_removed": len(removed),
            "by_segment": removed.groupby("flight_segment").size().to_dict(),
        }
