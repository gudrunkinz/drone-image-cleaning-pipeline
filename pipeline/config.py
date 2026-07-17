"""
pipeline/config.py
==================
Central configuration dataclass for the Drone Image Cleaning Pipeline.

All threshold parameters are documented here.  Edit this file to adapt
the pipeline to a different sensor, altitude, or field site.

Author : Gudrun Kinz
Contact: gudrun.kinz@students.boku.ac.at
License: MIT
"""

from dataclasses import dataclass, field
from typing import Tuple


@dataclass
class PipelineConfig:
    """
    Configuration parameters for the drone-image cleaning pipeline.

    Attributes
    ----------
    flight_gap_minutes : float
        Minimum time gap (minutes) between consecutive images that marks the
        start of a new flight segment.  Default: 10 min.

    yaw_threshold : float
        Images whose gimbal yaw is **below** this value (degrees) are
        classified as flying in the target direction (south→north for the
        BOKU Tulln wheat experiments).  Images at or above this threshold
        are rejected as flying in the opposite direction.  Default: 200°.

    min_altitude_m / max_altitude_m : float
        Absolute GPS altitude range (metres) for the survey.
        Images outside [min, max] are removed.  Default: 235–250 m.

    slope_tolerance_percent : float
        Maximum allowed perpendicular residual from the per-strip linear
        regression trendline, expressed as a percentage of the regression
        slope magnitude.  Default: 10 %.

    grubbs_alpha : float
        Significance level for Grubbs' iterative outlier test applied
        independently to gimbal roll, pitch, and yaw within each flight
        segment.  Default: 0.05.

    grubbs_max_iterations : int
        Upper bound on the number of outliers removed per angle per segment
        by the iterative Grubbs procedure.  Default: 10.

    pca_n_components : int
        Number of principal components retained for the optional PCA-based
        visual filtering stage.  Default: 3.

    pca_outlier_threshold : float
        Distance threshold (standard deviations from the PCA centroid) used
        to flag visually anomalous images.  Default: 3.0.

    pca_image_size : tuple
        Width × height (pixels) to which each image is downsampled before
        PCA feature extraction.  Default: (100, 100).

    duplicate_gps_threshold_m : float
        Maximum GPS distance (metres) between two images for them to be
        considered positional duplicates.  Default: 0.5 m.

    duplicate_angle_threshold_deg : float
        Maximum gimbal-angle difference (degrees) between two images for
        them to be considered orientation duplicates.  Default: 2°.

    output_base_dir : str
        Root directory for all pipeline outputs (logs, CSVs, figures).

    create_visualizations : bool
        If True, each stage saves a diagnostic plot.

    save_reports : bool
        If True, a plain-text summary report is written after the run.
    """

    # --- Stage 2: Flight Segmentation ---
    flight_gap_minutes: float = 10.0

    # --- Stage 3: Yaw Filtering ---
    yaw_threshold: float = 200.0

    # --- Stage 4: Altitude Filtering ---
    min_altitude_m: float = 235.0
    max_altitude_m: float = 250.0

    # --- Stage 5: Slope Filtering ---
    slope_tolerance_percent: float = 10.0

    # --- Stage 6: Grubbs' Test ---
    grubbs_alpha: float = 0.05
    grubbs_max_iterations: int = 10

    # --- Stage 7: PCA Visual Filtering (optional) ---
    pca_n_components: int = 3
    pca_outlier_threshold: float = 3.0
    pca_image_size: Tuple[int, int] = (100, 100)

    # --- Stage 8: Duplicate Filtering ---
    duplicate_gps_threshold_m: float = 0.5
    duplicate_angle_threshold_deg: float = 2.0

    # --- Output ---
    output_base_dir: str = "pipeline_output"
    create_visualizations: bool = True
    save_reports: bool = True
