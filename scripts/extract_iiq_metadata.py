#!/usr/bin/env python3
"""
extract_iiq_metadata.py
=======================
Extract flight-relevant metadata from Phase One IIQ (Intelligent Image Quality)
raw image files and export the results to a CSV file.

Primary method  : ExifTool (subprocess call) — reads all EXIF / XMP / MakerNotes
Fallback method : rawpy + piexif             — reads only standard EXIF IFDs

Usage
-----
1.  Set INPUT_DIR  to the folder that contains your .IIQ files.
2.  Set OUTPUT_CSV to the desired output path for the CSV file.
3.  Run:  python extract_iiq_metadata.py

Requirements
------------
    pip install rawpy piexif tqdm
    ExifTool must be installed and on the system PATH.
    Windows:  https://exiftool.org/  (rename exiftool(-k).exe → exiftool.exe)
    Linux:    sudo apt install libimage-exiftool-perl
    macOS:    brew install exiftool

Author  : Gudrun Kinz  (BOKU Vienna)
Version : 1.0  –  2025
"""

import csv
import json
import os
import subprocess
import sys
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
#  USER SETTINGS  ← change these two lines
# ─────────────────────────────────────────────────────────────────────────────

INPUT_DIR  = Path(r"C:\Users\YourName\Data\IIQ_Images")   # folder with .IIQ files
OUTPUT_CSV = Path(r"C:\Users\YourName\Data\iiq_metadata.csv")  # output CSV

# ─────────────────────────────────────────────────────────────────────────────
#  METADATA FIELDS TO EXTRACT
#  Keys are the ExifTool tag names (case-insensitive).
#  Values are the column headers written to the CSV.
# ─────────────────────────────────────────────────────────────────────────────

FIELDS = {
    # ── File identity ────────────────────────────────────────────────────────
    "FileName":                    "FileName",
    "FileSize":                    "FileSize_bytes",
    "FileModifyDate":              "FileModifyDate",

    # ── Capture timestamp ────────────────────────────────────────────────────
    "DateTimeOriginal":            "DateTimeOriginal",   # EXIF tag 0x9003
    "SubSecTimeOriginal":          "SubSecTimeOriginal", # EXIF tag 0x9291 (ms precision)
    "GPSDateStamp":                "GPS_DateStamp",
    "GPSTimeStamp":                "GPS_TimeStamp",

    # ── GPS position (WGS-84) ────────────────────────────────────────────────
    "GPSLatitude":                 "GPS_Latitude_deg",   # decimal degrees (ExifTool converts)
    "GPSLongitude":                "GPS_Longitude_deg",
    "GPSAltitude":                 "GPS_Altitude_m",     # metres above WGS-84 ellipsoid
    "GPSAltitudeRef":              "GPS_AltitudeRef",    # 0 = above sea level
    "GPSStatus":                   "GPS_Status",         # A = active fix

    # ── Absolute / relative altitude (DJI / Phase One XMP) ──────────────────
    # Phase One IXM writes these into the XMP-drone-dji namespace
    "AbsoluteAltitude":            "XMP_AbsoluteAltitude_m",   # ellipsoidal height
    "RelativeAltitude":            "XMP_RelativeAltitude_m",   # height above take-off

    # ── Gimbal orientation (XMP-drone-dji or XMP-Camera) ────────────────────
    "GimbalPitchDegree":           "XMP_GimbalPitch_deg",      # −90 = nadir
    "GimbalRollDegree":            "XMP_GimbalRoll_deg",
    "GimbalYawDegree":             "XMP_GimbalYaw_deg",        # compass heading

    # ── Flight controller / aircraft attitude ────────────────────────────────
    "FlightPitchDegree":           "XMP_FlightPitch_deg",
    "FlightRollDegree":            "XMP_FlightRoll_deg",
    "FlightYawDegree":             "XMP_FlightYaw_deg",

    # ── Camera / lens parameters ─────────────────────────────────────────────
    "Make":                        "Camera_Make",
    "Model":                       "Camera_Model",
    "SerialNumber":                "Camera_SerialNumber",
    "LensModel":                   "Lens_Model",
    "FocalLength":                 "FocalLength_mm",
    "FocalLengthIn35mmFormat":     "FocalLength35mm_mm",
    "FNumber":                     "FNumber",
    "ExposureTime":                "ExposureTime_s",
    "ISO":                         "ISO",
    "ExposureCompensation":        "ExposureComp_EV",

    # ── Image geometry ───────────────────────────────────────────────────────
    "ImageWidth":                  "ImageWidth_px",
    "ImageHeight":                 "ImageHeight_px",
    "BitsPerSample":               "BitsPerSample",

    # ── Phase One / IIQ-specific MakerNotes ─────────────────────────────────
    # ExifTool decodes Phase One MakerNotes under the "PhaseOne" group.
    "PhaseOne:CameraOrientation":  "PO_CameraOrientation",
    "PhaseOne:RawFormat":          "PO_RawFormat",          # IIQ-S, IIQ-L, IIQ-Sv2 …
    "PhaseOne:SensorTemperature":  "PO_SensorTemperature_C",
    "PhaseOne:FirmwareVersion":    "PO_FirmwareVersion",
    "PhaseOne:LensDistortion":     "PO_LensDistortion",

    # ── XMP – Phase One / Capture One ────────────────────────────────────────
    "XMP-crs:WhiteBalance":        "XMP_WhiteBalance",
    "XMP-crs:Temperature":         "XMP_ColorTemp_K",

    # ── Photogrammetry helpers ───────────────────────────────────────────────
    "XMP-Camera:RigCameraIndex":   "XMP_RigCameraIndex",    # multi-camera rigs
    "XMP-Camera:GPSXYAccuracy":    "XMP_GPS_XY_Accuracy_m",
    "XMP-Camera:GPSZAccuracy":     "XMP_GPS_Z_Accuracy_m",
}

# ─────────────────────────────────────────────────────────────────────────────
#  HELPER: check ExifTool availability
# ─────────────────────────────────────────────────────────────────────────────

def _check_exiftool() -> bool:
    """Return True if exiftool is reachable on the system PATH."""
    try:
        result = subprocess.run(
            ["exiftool", "-ver"],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


# ─────────────────────────────────────────────────────────────────────────────
#  PRIMARY METHOD: ExifTool via subprocess
# ─────────────────────────────────────────────────────────────────────────────

def extract_with_exiftool(iiq_path: Path) -> dict:
    """
    Call ExifTool on a single IIQ file and return a flat dict of tag → value.

    ExifTool is invoked with:
      -j          JSON output (one object per file)
      -n          Numeric output (avoids unit strings like '100 mm')
      -c "%.8f"   Decimal-degree GPS coordinates
      -G0         Include group name prefix (e.g. 'EXIF:', 'XMP-drone-dji:')
      --printConv Disable print-conversion so raw numeric values are returned
    """
    cmd = [
        "exiftool",
        "-j",           # JSON output
        "-n",           # numeric values, no units
        "-c", "%.8f",   # GPS decimal degrees with 8 decimal places
        "-G0",          # group prefix
        str(iiq_path),
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0:
            print(f"  [WARN] ExifTool error on {iiq_path.name}: {result.stderr.strip()}")
            return {}

        data_list = json.loads(result.stdout)
        if not data_list:
            return {}

        # ExifTool returns a list; take the first (and only) element
        raw = data_list[0]

        # Build a lookup that strips the group prefix for matching
        # e.g. "EXIF:GPSLatitude" → "GPSLatitude"
        stripped = {}
        for k, v in raw.items():
            # key may be "EXIF:GPSLatitude" or just "GPSLatitude"
            short_key = k.split(":")[-1] if ":" in k else k
            stripped[short_key] = v
            stripped[k] = v          # keep full key too for MakerNotes

        return stripped

    except subprocess.TimeoutExpired:
        print(f"  [WARN] ExifTool timed out on {iiq_path.name}")
        return {}
    except json.JSONDecodeError as e:
        print(f"  [WARN] JSON parse error for {iiq_path.name}: {e}")
        return {}


# ─────────────────────────────────────────────────────────────────────────────
#  FALLBACK METHOD: rawpy + piexif (standard EXIF only, no MakerNotes)
# ─────────────────────────────────────────────────────────────────────────────

def extract_with_rawpy(iiq_path: Path) -> dict:
    """
    Fallback: open IIQ with rawpy and read the embedded JPEG thumbnail's EXIF.
    Covers only standard EXIF tags (GPS, DateTimeOriginal, camera model …).
    Phase One MakerNotes and XMP blocks are NOT accessible via this path.
    """
    result = {}
    try:
        import rawpy      # pip install rawpy
        import piexif     # pip install piexif

        with rawpy.imread(str(iiq_path)) as raw:
            # rawpy exposes the embedded JPEG thumbnail
            thumb = raw.extract_thumb()

        if thumb.format == rawpy.ThumbFormat.JPEG:
            exif_dict = piexif.load(thumb.data)

            # GPS IFD
            gps = exif_dict.get("GPS", {})
            if piexif.GPSIFD.GPSLatitude in gps:
                lat_dms = gps[piexif.GPSIFD.GPSLatitude]
                lat_ref = gps.get(piexif.GPSIFD.GPSLatitudeRef, b"N").decode()
                lat = _dms_to_decimal(lat_dms, lat_ref)
                result["GPS_Latitude_deg"] = lat

            if piexif.GPSIFD.GPSLongitude in gps:
                lon_dms = gps[piexif.GPSIFD.GPSLongitude]
                lon_ref = gps.get(piexif.GPSIFD.GPSLongitudeRef, b"E").decode()
                lon = _dms_to_decimal(lon_dms, lon_ref)
                result["GPS_Longitude_deg"] = lon

            if piexif.GPSIFD.GPSAltitude in gps:
                alt_num, alt_den = gps[piexif.GPSIFD.GPSAltitude]
                result["GPS_Altitude_m"] = alt_num / alt_den if alt_den else None

            # Exif IFD
            exif = exif_dict.get("Exif", {})
            if piexif.ExifIFD.DateTimeOriginal in exif:
                result["DateTimeOriginal"] = exif[piexif.ExifIFD.DateTimeOriginal].decode()

            # 0th IFD (camera make / model)
            ifd0 = exif_dict.get("0th", {})
            if piexif.ImageIFD.Make in ifd0:
                result["Camera_Make"] = ifd0[piexif.ImageIFD.Make].decode(errors="replace").strip("\x00")
            if piexif.ImageIFD.Model in ifd0:
                result["Camera_Model"] = ifd0[piexif.ImageIFD.Model].decode(errors="replace").strip("\x00")

    except ImportError:
        print("  [WARN] rawpy / piexif not installed. Fallback unavailable.")
    except Exception as e:
        print(f"  [WARN] rawpy fallback failed for {iiq_path.name}: {e}")

    return result


# ─────────────────────────────────────────────────────────────────────────────
#  UTILITY: DMS → decimal degrees
# ─────────────────────────────────────────────────────────────────────────────

def _dms_to_decimal(dms_tuple, ref: str) -> float:
    """Convert EXIF DMS rational tuple to signed decimal degrees."""
    def _rat(r):
        return r[0] / r[1] if r[1] else 0.0
    d, m, s = [_rat(x) for x in dms_tuple]
    decimal = d + m / 60.0 + s / 3600.0
    if ref in ("S", "W"):
        decimal = -decimal
    return round(decimal, 8)


# ─────────────────────────────────────────────────────────────────────────────
#  CORE: process a single IIQ file
# ─────────────────────────────────────────────────────────────────────────────

def process_file(iiq_path: Path, use_exiftool: bool) -> dict:
    """
    Extract metadata from one IIQ file.
    Returns a flat dict with CSV column names as keys.
    """
    row = {"FileName": iiq_path.name}

    if use_exiftool:
        raw_tags = extract_with_exiftool(iiq_path)
        if not raw_tags:
            print(f"  [INFO] ExifTool returned nothing for {iiq_path.name}; trying rawpy fallback.")
            row.update(extract_with_rawpy(iiq_path))
            return row

        # Map ExifTool tag names → CSV column names
        for tag, col in FIELDS.items():
            # Try exact match first, then short-key match
            value = raw_tags.get(tag, raw_tags.get(tag.split(":")[-1], ""))
            if value != "":
                row[col] = value
    else:
        row.update(extract_with_rawpy(iiq_path))

    return row


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    # ── Validate input directory ─────────────────────────────────────────────
    if not INPUT_DIR.exists():
        sys.exit(f"[ERROR] INPUT_DIR does not exist: {INPUT_DIR}")

    iiq_files = sorted(INPUT_DIR.glob("*.IIQ")) + sorted(INPUT_DIR.glob("*.iiq"))
    if not iiq_files:
        sys.exit(f"[ERROR] No .IIQ files found in {INPUT_DIR}")

    print(f"Found {len(iiq_files)} IIQ file(s) in {INPUT_DIR}")

    # ── Check ExifTool availability ──────────────────────────────────────────
    use_exiftool = _check_exiftool()
    if use_exiftool:
        print("ExifTool detected — using primary extraction method.")
    else:
        print("[WARN] ExifTool not found. Falling back to rawpy + piexif.")
        print("       Phase One MakerNotes and XMP tags will NOT be available.")
        print("       Install ExifTool from https://exiftool.org/ for full metadata.")

    # ── Process all files ────────────────────────────────────────────────────
    # Collect all column names (preserving insertion order)
    all_cols = list(FIELDS.values())
    # Ensure FileName is first
    if "FileName" in all_cols:
        all_cols.remove("FileName")
    all_cols = ["FileName"] + all_cols

    rows = []

    # Optional progress bar (tqdm) — gracefully skip if not installed
    try:
        from tqdm import tqdm
        iterator = tqdm(iiq_files, desc="Extracting metadata", unit="file")
    except ImportError:
        iterator = iiq_files

    for iiq_path in iterator:
        row = process_file(iiq_path, use_exiftool)
        rows.append(row)

    # ── Write CSV ────────────────────────────────────────────────────────────
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=all_cols, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nDone. Metadata for {len(rows)} file(s) written to:\n  {OUTPUT_CSV}")

    # ── Quick sanity check ───────────────────────────────────────────────────
    gps_ok = sum(1 for r in rows if r.get("GPS_Latitude_deg"))
    alt_ok = sum(1 for r in rows if r.get("XMP_AbsoluteAltitude_m") or r.get("GPS_Altitude_m"))
    yaw_ok = sum(1 for r in rows if r.get("XMP_GimbalYaw_deg"))
    pitch_ok = sum(1 for r in rows if r.get("XMP_GimbalPitch_deg"))

    print(f"\n── Sanity check ──────────────────────────────────────")
    print(f"  GPS coordinates  : {gps_ok}/{len(rows)} files")
    print(f"  Altitude         : {alt_ok}/{len(rows)} files")
    print(f"  Gimbal yaw       : {yaw_ok}/{len(rows)} files")
    print(f"  Gimbal pitch     : {pitch_ok}/{len(rows)} files")
    print(f"──────────────────────────────────────────────────────")

    if gps_ok == 0:
        print("\n[WARN] No GPS data found. Possible causes:")
        print("  1. GPS fix was not acquired before capture.")
        print("  2. ExifTool is not installed (MakerNotes unavailable).")
        print("  3. IIQ files were stripped of metadata during transfer.")


if __name__ == "__main__":
    main()
