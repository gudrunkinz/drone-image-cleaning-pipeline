# Drone Image Cleaning Pipeline

A metadata-based pipeline for quality-filtering UAV images acquired during
wheat phenotyping campaigns.  The pipeline operates entirely on EXIF/XMP
metadata—no pixel-level processing is required—making it fast enough to
clean thousands of Phase One IIQ images in seconds.

> **Associated publication:**  
> Kinz G., Bürstmayr H., Roth P.M. (2026). *Automated Image Data Cleaning
> for UAV-Based Wheat Phenotyping Using Metadata Filtering.*
> *Remote Sensing*, MDPI. (under review)

---

## Pipeline Overview

```
IIQ images
    │
    ▼
[1] Metadata extraction  ──▶  metadata.csv          (scripts/extract_iiq_metadata.py)
    │
    ▼
[2] Flight segmentation  ──▶  assigns flight_segment IDs based on temporal gaps
    │
    ▼
[3] Yaw / direction filter  ──▶  removes return-direction transects (yaw ≥ 200°)
    │
    ▼
[4] Altitude filter  ──▶  removes images outside 235–250 m GPS altitude
    │
    ▼
[5] Slope / trajectory filter  ──▶  removes images deviating from linear flight path
    │
    ▼
[6] Grubbs' outlier detection  ──▶  removes gimbal-angle outliers per segment
    │
    ▼
cleaned_metadata.csv  +  removed_metadata.csv  +  cleaning_report.txt
```

Applied to the BOKU Tulln 2022 wheat phenotyping dataset (7 flight dates,
3,836 wheat-experiment images), the pipeline retained **2,737 images
(71.4%)** with an overall precision of 96.6 % and recall of 99.8 %
(validated against manual ground-truth labels, n = 1,112).

---

## Repository Structure

```
drone-image-cleaning-pipeline/
├── pipeline/                  # Core pipeline modules
│   ├── __init__.py
│   ├── config.py              # All threshold parameters
│   ├── flight_segmenter.py    # Stage 2
│   ├── yaw_filter.py          # Stage 3
│   ├── altitude_filter.py     # Stage 4
│   ├── slope_filter.py        # Stage 5
│   └── grubbs_filter.py       # Stage 6
├── scripts/
│   ├── extract_iiq_metadata.py   # Stage 1: IIQ → CSV
│   └── run_pipeline.py           # Command-line entry point
├── data/
│   └── example/
│       └── example_metadata.csv  # 20-row anonymised sample
├── tests/
│   └── test_filters.py
├── README.md
├── requirements.txt
├── CITATION.cff
└── LICENSE
```

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

ExifTool must also be installed separately (used by Stage 1):

- **Windows:** download from <https://exiftool.org> and add to PATH  
- **Linux/macOS:** `sudo apt install libimage-exiftool-perl`  (or `brew install exiftool`)

### 2. Extract metadata from IIQ files (Stage 1)

Edit the paths at the top of the script, then run:

```bash
python scripts/extract_iiq_metadata.py
```

This produces `metadata.csv` with columns:
`Image_id, File Name, timestamp, latitude, longitude, altitude,
pitch, roll, yaw, flight_date, flight_segment`

### 3. Run the cleaning pipeline (Stages 2–6)

```bash
python scripts/run_pipeline.py \
    --input metadata.csv \
    --output pipeline_output/
```

Outputs written to `pipeline_output/`:
- `cleaned_metadata.csv`   — kept images
- `removed_metadata.csv`   — removed images with reason column
- `cleaning_report.txt`    — plain-text summary
- `pipeline_<ts>.log`      — full run log

### 4. Run on the example data

```bash
python scripts/run_pipeline.py \
    --input data/example/example_metadata.csv \
    --output pipeline_output_example/
```

---

## Configuration

All thresholds live in `pipeline/config.py`.  You can override them
without editing the source by passing a JSON file:

```json
{
    "yaw_threshold": 190.0,
    "min_altitude_m": 230.0,
    "max_altitude_m": 255.0,
    "grubbs_alpha": 0.01
}
```

```bash
python scripts/run_pipeline.py \
    --input metadata.csv \
    --config my_config.json \
    --output output/
```

---

## Input CSV Format

The pipeline expects a CSV with **at minimum** these columns:

| Column           | Type     | Description                              |
|------------------|----------|------------------------------------------|
| `Image_id`       | string   | Unique image identifier                  |
| `File Name`      | string   | Original filename (e.g. P0000092.IIQ)    |
| `timestamp`      | datetime | Capture time (YYYY-MM-DD HH:MM:SS)       |
| `latitude`       | float    | GPS latitude (decimal degrees, WGS-84)   |
| `longitude`      | float    | GPS longitude (decimal degrees, WGS-84)  |
| `altitude`       | float    | GPS altitude (metres, ellipsoidal)       |
| `pitch`          | float    | Gimbal pitch (degrees)                   |
| `roll`           | float    | Gimbal roll (degrees)                    |
| `yaw`            | float    | Gimbal yaw / compass heading (0–360°)    |
| `flight_date`    | string   | Date string (YYYY-MM-DD)                 |

See `data/example/example_metadata.csv` for a concrete example.

---

## Adapting to Other Sensors / Sites

The pipeline is sensor-agnostic; only the thresholds in `config.py` are
site-specific.  To adapt it:

1. Set `yaw_threshold` to the heading value that separates your two
   flight directions.
2. Set `min_altitude_m` / `max_altitude_m` to your survey altitude ± a
   suitable margin.
3. Adjust `grubbs_alpha` if your gimbal is less stable (lower α = fewer
   removals).
4. Set `flight_gap_minutes` to match your actual inter-flight gap.

---

## Running Tests

```bash
pytest tests/
```

---

## Citation

If you use this pipeline in your research, please cite:

```
Kinz G., Bürstmayr H., Roth P.M. (2026).
Automated Image Data Cleaning for UAV-Based Wheat Phenotyping
Using Metadata Filtering.
Remote Sensing, MDPI. https://doi.org/10.XXXX/rsXXXXXXXX
```

A machine-readable citation is provided in `CITATION.cff`.

---

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE).
