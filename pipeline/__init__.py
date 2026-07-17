"""
drone-image-cleaning-pipeline
==============================
A metadata-based image data cleaning pipeline for UAV wheat phenotyping.

Stages
------
1. Metadata extraction   (see scripts/extract_iiq_metadata.py)
2. Flight segmentation   (FlightSegmenter)
3. Yaw / direction filter (YawFilter)
4. Altitude filter        (AltitudeFilter)
5. Slope / trajectory filter (SlopeFilter)
6. Grubbs' outlier test   (GrubbsFilter)
7. PCA visual filter      (optional – PCAVisualFilter)
8. Duplicate filter       (optional – DuplicateFilter)

Quick start
-----------
>>> from pipeline import PipelineConfig, run_cleaning_pipeline
>>> cfg = PipelineConfig(output_base_dir="my_output")
>>> cleaned_df = run_cleaning_pipeline("metadata.csv", cfg)
"""

from .config           import PipelineConfig
from .flight_segmenter import FlightSegmenter
from .yaw_filter        import YawFilter
from .altitude_filter   import AltitudeFilter
from .slope_filter      import SlopeFilter
from .grubbs_filter     import GrubbsFilter

__all__ = [
    "PipelineConfig",
    "FlightSegmenter",
    "YawFilter",
    "AltitudeFilter",
    "SlopeFilter",
    "GrubbsFilter",
]

__version__ = "1.0.0"
__author__  = "Gudrun Kinz"
