"""
scripts/run_pipeline.py
========================
Drone Image Cleaning Pipeline — IDE Starter

How to use in PyCharm / VS Code / Spyder
-----------------------------------------
1. Open this file.
2. Fill in your paths and parameters under "USER SETTINGS".
3. Press the green Run button (or F5).

Output written to OUTPUT_DIR:
    cleaned_metadata.csv   — retained images  (stage = 'kept')
    removed_metadata.csv   — discarded images (stage = 'removed')
    cleaning_report.txt    — plain-text summary
    pipeline_<date>.log    — full run log

Author : Gudrun Kinz
License: MIT
"""

import logging
import os
import sys
from datetime import datetime

import pandas as pd

# Ensure the 'pipeline/' package is importable regardless of working directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import (
    PipelineConfig,
    FlightSegmenter,
    YawFilter,
    AltitudeFilter,
    SlopeFilter,
    GrubbsFilter,
)


# =============================================================================
#  USER SETTINGS — edit this block, then press the green Run button
# =============================================================================

# Path to the input metadata CSV (produced by scripts/extract_iiq_metadata.py)
INPUT_CSV = r"C:\Users\YourName\Data\metadata.csv"

# Folder for all outputs (created automatically if it does not exist)
OUTPUT_DIR = r"C:\Users\YourName\Data\pipeline_output"

# Process only a specific flight date?
# Set to None to process ALL dates.
FILTER_DATE = None          # Example: "2022-06-22"  or  None

# --------------------------------------------------------------------------
#  Pipeline parameters  (defaults are validated for the BOKU Tulln dataset)
# --------------------------------------------------------------------------
YAW_THRESHOLD   = 200.0   # degrees: images with yaw >= this value are removed
MIN_ALTITUDE_M  = 235.0   # minimum GPS altitude in metres
MAX_ALTITUDE_M  = 250.0   # maximum GPS altitude in metres
FLIGHT_GAP_MIN  = 10.0    # time gap (minutes) that starts a new flight segment
SLOPE_TOLERANCE = 10.0    # trajectory tolerance as % of regression slope
GRUBBS_ALPHA    = 0.05    # significance level for the Grubbs outlier test
GRUBBS_MAX_ITER = 10      # max outliers removed per segment and angle

# =============================================================================
#  DO NOT EDIT BELOW THIS LINE
# =============================================================================


def setup_logging(output_dir: str) -> logging.Logger:
    """Configure logging to both file and console."""
    os.makedirs(output_dir, exist_ok=True)
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(output_dir, f"pipeline_{ts}.log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger("pipeline")


def _print_summary_table(df: pd.DataFrame, logger: logging.Logger):
    """Log a per-date retention summary table to the console and log file."""
    logger.info("")
    logger.info("=" * 70)
    logger.info("SUMMARY BY FLIGHT DATE")
    logger.info(f"{'Date':<14} {'Input':>6} {'Yaw':>6} {'Alt':>6} "
                f"{'Slope':>6} {'Grubbs':>7} {'Kept':>6} {'Ret%':>7}")
    logger.info("-" * 70)

    for date, grp in df.groupby("flight_date"):
        total   = len(grp)
        yaw_n   = (grp["removal_reason"] == "other_direction").sum()
        alt_n   = (grp["removal_reason"] == "altitude_out_of_range").sum()
        slope_n = (grp["removal_reason"] == "trajectory_deviation").sum()
        grub_n  = (grp["removal_reason"] == "grubbs_outlier").sum()
        kept    = (grp["stage"] == "kept").sum()
        pct     = 100.0 * kept / total if total > 0 else 0.0
        logger.info(
            f"{str(date):<14} {total:>6} {yaw_n:>6} {alt_n:>6} "
            f"{slope_n:>6} {grub_n:>7} {kept:>6} {pct:>6.1f}%"
        )

    logger.info("-" * 70)
    total = len(df)
    kept  = (df["stage"] == "kept").sum()
    pct   = 100.0 * kept / total if total > 0 else 0.0
    logger.info(
        f"{'TOTAL':<14} {total:>6} "
        f"{(df['removal_reason'] == 'other_direction').sum():>6} "
        f"{(df['removal_reason'] == 'altitude_out_of_range').sum():>6} "
        f"{(df['removal_reason'] == 'trajectory_deviation').sum():>6} "
        f"{(df['removal_reason'] == 'grubbs_outlier').sum():>7} "
        f"{kept:>6} {pct:>6.1f}%"
    )
    logger.info("=" * 70)


def run_cleaning_pipeline(
    input_csv:   str,
    config:      PipelineConfig,
    logger:      logging.Logger,
    filter_date: str = None,
) -> pd.DataFrame:
    """
    Execute stages 2–6 on a metadata CSV and return the annotated DataFrame.

    Parameters
    ----------
    input_csv   : Path to metadata CSV with columns:
                  Image_id, File Name, timestamp, latitude, longitude,
                  altitude, pitch, roll, yaw, flight_date
    config      : PipelineConfig instance (built from USER SETTINGS above)
    logger      : Logger instance
    filter_date : If given, only rows matching this flight_date are processed.

    Returns
    -------
    pd.DataFrame with added / updated columns:
        stage            — 'kept' or 'removed'
        removal_reason   — reason for removal (empty for kept images)
        time_diff        — time since previous image in minutes
        flight_segment   — zero-based integer segment index
    """
    logger.info("=" * 70)
    logger.info("DRONE IMAGE CLEANING PIPELINE  v1.0")
    logger.info(f"Input  : {input_csv}")
    logger.info(f"Output : {config.output_base_dir}")
    logger.info("=" * 70)

    # --- Load data ---------------------------------------------------------
    df = pd.read_csv(input_csv, parse_dates=["timestamp"])

    if filter_date:
        df = df[df["flight_date"].astype(str) == filter_date].copy()
        logger.info(f"Filtered to date {filter_date}: {len(df)} images")

    if len(df) == 0:
        logger.error("No images to process. "
                     "Please check INPUT_CSV and FILTER_DATE.")
        return df

    # Initialise annotation columns if not already present
    if "stage" not in df.columns:
        df["stage"]          = "kept"
    if "removal_reason" not in df.columns:
        df["removal_reason"] = ""

    logger.info(f"Loaded {len(df)} images")

    # --- Stage 2: Flight Segmentation -------------------------------------
    df = FlightSegmenter(config, logger).segment_flights(df)

    # --- Stage 3: Yaw Filter ----------------------------------------------
    df = YawFilter(config, logger).filter(df)

    # --- Stage 4: Altitude Filter -----------------------------------------
    df = AltitudeFilter(config, logger).filter(df)

    # --- Stage 5: Slope / Trajectory Filter --------------------------------
    df = SlopeFilter(config, logger).filter(df)

    # --- Stage 6: Grubbs' Outlier Detection --------------------------------
    df = GrubbsFilter(config, logger).filter(df)

    # --- Final annotation -------------------------------------------------
    df.loc[df["stage"] != "removed", "stage"] = "kept"

    # --- Save outputs ------------------------------------------------------
    os.makedirs(config.output_base_dir, exist_ok=True)

    cleaned_csv = os.path.join(config.output_base_dir, "cleaned_metadata.csv")
    removed_csv = os.path.join(config.output_base_dir, "removed_metadata.csv")
    report_txt  = os.path.join(config.output_base_dir, "cleaning_report.txt")

    kept_df    = df[df["stage"] == "kept"]
    removed_df = df[df["stage"] == "removed"]

    kept_df.to_csv(cleaned_csv,    index=False)
    removed_df.to_csv(removed_csv, index=False)

    logger.info(f"Saved cleaned  metadata → {cleaned_csv}  ({len(kept_df)} rows)")
    logger.info(f"Saved removed  metadata → {removed_csv}  ({len(removed_df)} rows)")

    # --- Print summary table ----------------------------------------------
    _print_summary_table(df, logger)

    total = len(df)
    kept  = len(kept_df)
    pct   = 100.0 * kept / total
    logger.info(f"\nOverall retention: {kept}/{total} images = {pct:.1f}%")

    # Plain-text report
    with open(report_txt, "w", encoding="utf-8") as fh:
        fh.write("Drone Image Cleaning Pipeline — Report\n")
        fh.write(f"Generated : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        fh.write(f"Input CSV : {input_csv}\n")
        fh.write(f"Total     : {total}\n")
        fh.write(f"Kept      : {kept}  ({pct:.1f}%)\n")
        fh.write(f"Removed   : {total - kept}\n\n")
        fh.write("Removal breakdown:\n")
        for reason, cnt in removed_df["removal_reason"].value_counts().items():
            fh.write(f"  {reason:<30} {cnt:>6}\n")

    logger.info(f"Saved report            → {report_txt}")
    return df


# =============================================================================
#  ENTRY POINT — executed when you press the green Run button
# =============================================================================

if __name__ == "__main__":

    # Build the configuration from the USER SETTINGS defined at the top
    config = PipelineConfig(
        flight_gap_minutes      = FLIGHT_GAP_MIN,
        yaw_threshold           = YAW_THRESHOLD,
        min_altitude_m          = MIN_ALTITUDE_M,
        max_altitude_m          = MAX_ALTITUDE_M,
        slope_tolerance_percent = SLOPE_TOLERANCE,
        grubbs_alpha            = GRUBBS_ALPHA,
        grubbs_max_iterations   = GRUBBS_MAX_ITER,
        output_base_dir         = OUTPUT_DIR,
    )

    logger = setup_logging(OUTPUT_DIR)

    run_cleaning_pipeline(
        input_csv   = INPUT_CSV,
        config      = config,
        logger      = logger,
        filter_date = FILTER_DATE,
    )
