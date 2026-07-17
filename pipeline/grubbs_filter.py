"""
pipeline/grubbs_filter.py
==========================
Stage 6 — Grubbs' Outlier Detection

Detects statistically extreme gimbal-orientation values within each
flight segment using the iterative Grubbs' test (Grubbs, 1969).

The test is applied independently to three gimbal angles:
  - roll  (lateral tilt)
  - pitch (forward tilt; should stay near –45° for nadir+oblique setup)
  - yaw   (compass heading; already pre-filtered in Stage 3)

Iterative application: after each detected outlier is removed the test
is re-run on the remaining data until either no more outliers are found
or ``grubbs_max_iterations`` is reached.

Reference
---------
Grubbs, F. E. (1969). Procedures for detecting outlying observations
in samples. *Technometrics*, 11(1), 1–21.
https://doi.org/10.1080/00401706.1969.10490657

Author : Gudrun Kinz
License: MIT
"""

import logging
from typing import List, Tuple

import numpy as np
import pandas as pd
from scipy import stats

from .config import PipelineConfig


class GrubbsFilter:
    """
    Iterative Grubbs' outlier detector applied to gimbal angles.

    Parameters
    ----------
    config : PipelineConfig
        Uses ``grubbs_alpha`` and ``grubbs_max_iterations``.
    logger : logging.Logger
    """

    def __init__(self, config: PipelineConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger

    # ------------------------------------------------------------------
    @staticmethod
    def _grubbs_test(data: np.ndarray, alpha: float) -> Tuple[bool, int]:
        """
        Single-pass Grubbs' test.

        Parameters
        ----------
        data  : 1-D array of numeric values
        alpha : significance level (e.g. 0.05)

        Returns
        -------
        (is_outlier : bool, outlier_index : int)
            ``outlier_index`` is –1 when no outlier is detected or
            the sample is too small (< 3).
        """
        n = len(data)
        if n < 3:
            return False, -1

        mean = np.mean(data)
        std  = np.std(data, ddof=1)

        if std == 0:
            return False, -1

        abs_diff  = np.abs(data - mean)
        max_idx   = int(np.argmax(abs_diff))
        G_stat    = abs_diff[max_idx] / std

        # Two-sided critical value
        t_crit = stats.t.ppf(1.0 - alpha / (2.0 * n), df=n - 2)
        G_crit = (
            (n - 1) / np.sqrt(n)
            * np.sqrt(t_crit**2 / (n - 2 + t_crit**2))
        )

        return G_stat > G_crit, max_idx

    # ------------------------------------------------------------------
    def _find_outliers(self, data: np.ndarray) -> List[int]:
        """
        Iteratively find outlier indices in a 1-D array.

        Returns
        -------
        List of original array indices that are outliers.
        """
        outlier_indices: List[int] = []
        remaining_data    = data.copy()
        remaining_indices = np.arange(len(data))

        for _ in range(self.config.grubbs_max_iterations):
            is_out, local_idx = self._grubbs_test(
                remaining_data, self.config.grubbs_alpha
            )
            if not is_out:
                break

            original_idx = int(remaining_indices[local_idx])
            outlier_indices.append(original_idx)

            remaining_data    = np.delete(remaining_data, local_idx)
            remaining_indices = np.delete(remaining_indices, local_idx)

            if len(remaining_data) < 3:
                break

        return outlier_indices

    # ------------------------------------------------------------------
    def filter(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply Grubbs' test per flight segment and per gimbal angle.

        Only active (not yet removed) rows are tested.

        Parameters
        ----------
        df : pd.DataFrame
            Must contain ``roll``, ``pitch``, ``yaw``,
            ``flight_segment``, and ``stage`` columns.

        Returns
        -------
        pd.DataFrame
            Outlier rows tagged stage='removed',
            removal_reason='grubbs_outlier'.
        """
        self.logger.info("Stage 6 — Grubbs' Outlier Detection")
        self.logger.info(
            f"  alpha = {self.config.grubbs_alpha}, "
            f"max iterations = {self.config.grubbs_max_iterations}"
        )

        active = df[df["stage"] != "removed"]
        all_out_global: set = set()

        for seg_id in active["flight_segment"].unique():
            seg_df    = active[active["flight_segment"] == seg_id]
            seg_index = seg_df.index  # global pandas index

            for angle in ("roll", "pitch", "yaw"):
                data       = seg_df[angle].values
                local_outs = self._find_outliers(data)

                if local_outs:
                    global_outs = seg_index[local_outs].tolist()
                    all_out_global.update(global_outs)
                    self.logger.info(
                        f"  Segment {seg_id}, {angle}: "
                        f"{len(local_outs)} outlier(s) detected"
                    )

        out_idx = list(all_out_global)
        df.loc[out_idx, "stage"]          = "removed"
        df.loc[out_idx, "removal_reason"] = "grubbs_outlier"

        n_active  = len(active)
        n_removed = len(out_idx)
        n_kept    = n_active - n_removed

        self.logger.info(
            f"  Kept {n_kept}/{n_active} active images  "
            f"({100*n_kept/n_active:.1f}%)  —  "
            f"removed {n_removed} (Grubbs outliers)"
        )

        return df

    # ------------------------------------------------------------------
    @staticmethod
    def summary(df: pd.DataFrame) -> dict:
        """Return a dict with per-segment removal counts."""
        removed = df[df["removal_reason"] == "grubbs_outlier"]
        return {
            "total_removed": len(removed),
            "by_segment": removed.groupby("flight_segment").size().to_dict(),
        }
