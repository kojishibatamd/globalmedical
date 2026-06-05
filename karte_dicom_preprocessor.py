#!/usr/bin/env python3
import argparse
import hashlib
import json
import math
import re
import shutil
import sys
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pydicom
from PIL import Image
from pydicom.errors import InvalidDicomError


SCHEMA_VERSION = "0.1"
CREATED_BY = "Global Medical KARTE DICOM Preprocessor"


@dataclass
class DicomItem:
    path: Path
    rel_path: str
    study_uid: str
    series_uid: str
    modality: str
    series_description: str
    body_part_examined: str
    image_type: str
    instance_number: Optional[float]
    image_position_patient: Optional[tuple[float, float, float]]
    image_orientation_patient: Optional[tuple[float, float, float, float, float, float]]
    slice_location: Optional[float]
    series_number: Optional[float]


@dataclass
class SeriesGroup:
    study_uid: str
    series_uid: str
    items: list[DicomItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def sanitize_filename(value: str, fallback: str = "NoDescription") -> str:
    value = (value or "").strip()
    if not value:
        return fallback
    safe = re.sub(r"[^\w.-]+", "_", value, flags=re.ASCII)
    safe = re.sub(r"_+", "_", safe).strip("._-")
    return safe[:80] or fallback


def dicom_date_to_iso(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    if not re.fullmatch(r"\d{8}", text):
        return None
    return f"{text[0:4]}-{text[4:6]}-{text[6:8]}"


def get_first(value: Any) -> Any:
    if isinstance(value, (list, tuple)) or value.__class__.__name__ == "MultiValue":
        return value[0] if value else None
    return value


def to_float(value: Any) -> Optional[float]:
    try:
        value = get_first(value)
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def to_float_tuple(value: Any, length: int) -> Optional[tuple[float, ...]]:
    try:
        if value is None or len(value) != length:
            return None
        return tuple(float(v) for v in value)
    except (TypeError, ValueError):
        return None


def value_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)) or value.__class__.__name__ == "MultiValue":
        return "\\".join(str(v) for v in value)
    return str(value)


def discover_files(input_dir: Path) -> list[Path]:
    return sorted(path for path in input_dir.rglob("*") if path.is_file())


def read_dicom_headers(input_dir: Path) -> tuple[list[DicomItem], int]:
    items: list[DicomItem] = []
    unreadable = 0

    for path in discover_files(input_dir):
        rel_path = str(path.relative_to(input_dir))
        try:
            ds = pydicom.dcmread(path, stop_before_pixels=True)
        except (InvalidDicomError, OSError, Exception):
            unreadable += 1
            continue

        study_uid = str(getattr(ds, "StudyInstanceUID", "") or "")
        series_uid = str(getattr(ds, "SeriesInstanceUID", "") or "")
        if not study_uid or not series_uid:
            unreadable += 1
            continue

        items.append(
            DicomItem(
                path=path,
                rel_path=rel_path,
                study_uid=study_uid,
                series_uid=series_uid,
                modality=str(getattr(ds, "Modality", "") or "Unknown"),
                series_description=str(getattr(ds, "SeriesDescription", "") or ""),
                body_part_examined=str(getattr(ds, "BodyPartExamined", "") or ""),
                image_type=value_text(getattr(ds, "ImageType", "")),
                instance_number=to_float(getattr(ds, "InstanceNumber", None)),
                image_position_patient=to_float_tuple(
                    getattr(ds, "ImagePositionPatient", None), 3
                ),
                image_orientation_patient=to_float_tuple(
                    getattr(ds, "ImageOrientationPatient", None), 6
                ),
                slice_location=to_float(getattr(ds, "SliceLocation", None)),
                series_number=to_float(getattr(ds, "SeriesNumber", None)),
            )
        )

    return items, unreadable


def group_series(items: list[DicomItem]) -> list[SeriesGroup]:
    groups: dict[tuple[str, str], SeriesGroup] = {}
    for item in items:
        key = (item.study_uid, item.series_uid)
        groups.setdefault(key, SeriesGroup(item.study_uid, item.series_uid)).items.append(item)

    return sorted(
        groups.values(),
        key=lambda group: (
            sha256_text(group.study_uid),
            group.items[0].series_number if group.items[0].series_number is not None else math.inf,
            group.items[0].modality,
            group.items[0].series_description,
            sha256_text(group.series_uid),
        ),
    )


def sort_key_image_position(item: DicomItem) -> tuple:
    ipp = item.image_position_patient
    if ipp is None:
        return (math.inf, item.rel_path)

    orientation = item.image_orientation_patient
    if orientation:
        row = np.array(orientation[:3], dtype=float)
        col = np.array(orientation[3:], dtype=float)
        normal = np.cross(row, col)
        position = float(np.dot(normal, np.array(ipp, dtype=float)))
        return (position, item.rel_path)

    return (ipp[2], ipp[1], ipp[0], item.rel_path)


def sort_series_items(series: SeriesGroup) -> tuple[list[DicomItem], str]:
    items = series.items
    if all(item.image_position_patient is not None for item in items):
        return sorted(items, key=sort_key_image_position), "ImagePositionPatient"
    if all(item.slice_location is not None for item in items):
        return sorted(items, key=lambda item: (item.slice_location, item.rel_path)), "SliceLocation"
    if all(item.instance_number is not None for item in items):
        return sorted(items, key=lambda item: (item.instance_number, item.rel_path)), "InstanceNumber"
    return sorted(items, key=lambda item: item.rel_path), "filename"


def list_series(series_groups: list[SeriesGroup]) -> None:
    print("Series一覧")
    print(
        "No\tModality\tSeriesDescription\tBodyPartExamined\tImageType\t"
        "Images\tInstanceRange\tHasIPP\tHasSliceLocation\tSortMethod"
    )
    for idx, group in enumerate(series_groups, start=1):
        items, sort_method = sort_series_items(group)
        first = items[0]
        instance_values = [item.instance_number for item in items if item.instance_number is not None]
        if instance_values:
            instance_range = f"{int(min(instance_values))}-{int(max(instance_values))}"
        else:
            instance_range = "-"
        print(
            "\t".join(
                [
                    str(idx),
                    first.modality or "-",
                    first.series_description or "-",
                    first.body_part_examined or "-",
                    first.image_type or "-",
                    str(len(items)),
                    instance_range,
                    "yes" if any(item.image_position_patient is not None for item in items) else "no",
                    "yes" if any(item.slice_location is not None for item in items) else "no",
                    sort_method,
                ]
            )
        )


def window_values(ds: pydicom.dataset.Dataset, pixel_data: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    slope = float(get_first(getattr(ds, "RescaleSlope", 1)) or 1)
    intercept = float(get_first(getattr(ds, "RescaleIntercept", 0)) or 0)
    image = pixel_data.astype(np.float32) * slope + intercept

    center = to_float(getattr(ds, "WindowCenter", None))
    width = to_float(getattr(ds, "WindowWidth", None))
    if center is not None and width is not None and width > 0:
        lower = center - width / 2
        upper = center + width / 2
        method = "DICOM_WindowCenter_WindowWidth"
    else:
        finite = image[np.isfinite(image)]
        if finite.size == 0:
            lower, upper = 0.0, 1.0
        else:
            lower, upper = np.percentile(finite, [1, 99]).astype(float)
            if lower == upper:
                upper = lower + 1.0
        center = None
        width = None
        method = "percentile"

    image = np.clip((image - lower) / (upper - lower), 0, 1) * 255
    if str(getattr(ds, "PhotometricInterpretation", "")).upper() == "MONOCHROME1":
        image = 255 - image

    return image.astype(np.uint8), {
        "method": method,
        "window_center": center,
        "window_width": width,
    }


def pixel_array_to_grayscale(ds: pydicom.dataset.Dataset) -> np.ndarray:
    array = ds.pixel_array
    array = np.asarray(array)
    array = np.squeeze(array)
    if array.ndim == 3 and array.shape[-1] in (3, 4):
        array = array[..., :3].mean(axis=-1)
    elif array.ndim > 2:
        array = array[0]
    if array.ndim != 2:
        raise ValueError(f"unsupported pixel array shape: {array.shape}")
    return array


def save_images(image_8bit: np.ndarray, display_path: Path, thumb_path: Path, display_width: int, thumb_size: int) -> None:
    image = Image.fromarray(image_8bit)

    display = image.copy()
    if display.width > display_width:
        height = max(1, round(display.height * (display_width / display.width)))
        display = display.resize((display_width, height), Image.Resampling.LANCZOS)

    thumb = image.copy()
    thumb.thumbnail((thumb_size, thumb_size), Image.Resampling.LANCZOS)

    display.save(display_path, format="JPEG", quality=90, optimize=True)
    thumb.save(thumb_path, format="JPEG", quality=85, optimize=True)


def modality_summary(modalities: set[str]) -> str:
    clean = {m for m in modalities if m and m != "Unknown"}
    if {"PT", "PET", "CT"} & clean and "CT" in clean:
        return "PET-CT"
    return "-".join(sorted(clean)) if clean else "Unknown"


def zip_directory(source_dir: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(source_dir.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(source_dir.parent))


def convert_series(
    selected_groups: list[tuple[int, SeriesGroup]],
    output_dir: Path,
    display_width: int,
    thumb_size: int,
    series_labels: dict[int, str],
) -> tuple[Path, dict[str, Any]]:
    first_study_uid = selected_groups[0][1].study_uid
    study_hash = sha256_text(first_study_uid)[:16]
    upload_dir = output_dir / f"KARTE_UPLOAD_{study_hash}"
    if upload_dir.exists():
        shutil.rmtree(upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    all_warnings: list[str] = []
    metadata_series = []
    study_date: Optional[str] = None
    modalities: set[str] = set()

    for output_index, (source_series_index, group) in enumerate(selected_groups, start=1):
        items, sort_method = sort_series_items(group)
        first = items[0]
        modalities.add(first.modality)
        desc_sanitized = sanitize_filename(first.series_description)
        modality = sanitize_filename(first.modality, "Unknown")
        series_name = f"series_{output_index:03d}_{modality}_{desc_sanitized}"
        patient_display_name = series_labels.get(source_series_index) or desc_sanitized or series_name
        display_dir = upload_dir / series_name / "display"
        thumb_dir = upload_dir / series_name / "thumb"
        display_dir.mkdir(parents=True, exist_ok=True)
        thumb_dir.mkdir(parents=True, exist_ok=True)

        windowing: Optional[dict[str, Any]] = None
        converted_count = 0

        for image_index, item in enumerate(items, start=1):
            try:
                ds = pydicom.dcmread(item.path)
                if study_date is None:
                    study_date = dicom_date_to_iso(getattr(ds, "StudyDate", None))
                grayscale = pixel_array_to_grayscale(ds)
                image_8bit, current_windowing = window_values(ds, grayscale)
                if windowing is None:
                    windowing = current_windowing
                filename = f"{image_index:04d}.jpg"
                save_images(
                    image_8bit,
                    display_dir / filename,
                    thumb_dir / filename,
                    display_width,
                    thumb_size,
                )
                converted_count += 1
            except Exception as exc:
                warning = f"{item.rel_path}: pixel conversion failed: {exc}"
                group.warnings.append(warning)
                all_warnings.append(warning)
                continue

        metadata_series.append(
            {
                "series_index": output_index,
                "source_series_number": source_series_index,
                "series_uid_hash": sha256_text(group.series_uid),
                "series_name": series_name,
                "modality": first.modality,
                "series_description_sanitized": desc_sanitized,
                "patient_display_name": patient_display_name,
                "image_count": converted_count,
                "display_dir": f"{series_name}/display",
                "thumb_dir": f"{series_name}/thumb",
                "sort_method": sort_method,
                "reverse_order": False,
                "image_width": display_width,
                "thumbnail_size": thumb_size,
                "windowing": windowing
                or {
                    "method": "unavailable",
                    "window_center": None,
                    "window_width": None,
                },
                "warnings": group.warnings,
            }
        )

    metadata = {
        "schema_version": SCHEMA_VERSION,
        "source_type": "DICOM-derived",
        "created_by": CREATED_BY,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "study": {
            "study_uid_hash": sha256_text(first_study_uid),
            "study_date": study_date,
            "modality_summary": modality_summary(modalities),
            "series_count": len(metadata_series),
        },
        "series": metadata_series,
        "warnings": all_warnings,
    }
    (upload_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return upload_dir, metadata


def parse_include_series(value: Optional[str], max_series: int) -> Optional[set[int]]:
    if not value:
        return None
    indexes: set[int] = set()
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            index = int(part)
        except ValueError as exc:
            raise ValueError(f"invalid --include-series value: {part}") from exc
        if index < 1 or index > max_series:
            raise ValueError(f"--include-series index out of range: {index}")
        indexes.add(index)
    return indexes


def parse_series_labels(value: Optional[str], max_series: int) -> dict[int, str]:
    if not value:
        return {}
    labels: dict[int, str] = {}
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" not in part:
            raise ValueError(f"invalid --series-labels item: {part}")
        index_text, label = part.split(":", 1)
        try:
            index = int(index_text.strip())
        except ValueError as exc:
            raise ValueError(f"invalid --series-labels series number: {index_text}") from exc
        if index < 1 or index > max_series:
            raise ValueError(f"--series-labels index out of range: {index}")
        label = label.strip()
        if not label:
            raise ValueError(f"--series-labels label is empty for series: {index}")
        labels[index] = label
    return labels


def main() -> int:
    parser = argparse.ArgumentParser(
        description="KARTE upload ZIP preprocessor for anonymized DICOM studies."
    )
    parser.add_argument("--input", required=True, help="Input DICOM directory")
    parser.add_argument("--output", required=True, help="Output directory")
    parser.add_argument("--display-width", type=int, default=1024, help="Max display image width")
    parser.add_argument("--thumb-size", type=int, default=256, help="Thumbnail max side length")
    parser.add_argument("--list-series", action="store_true", help="List series and exit")
    parser.add_argument("--include-series", help="Comma-separated series numbers to convert")
    parser.add_argument(
        "--series-labels",
        help='Patient display labels by list-series number, e.g. "2:胸部CT,3:PET横断像"',
    )
    parser.add_argument("--zip", action="store_true", help="Create KARTE_UPLOAD zip")
    args = parser.parse_args()

    input_dir = Path(args.input).expanduser().resolve()
    output_dir = Path(args.output).expanduser().resolve()

    if not input_dir.is_dir():
        print(f"ERROR: input directory not found: {input_dir}", file=sys.stderr)
        return 1
    if args.display_width < 1 or args.thumb_size < 1:
        print("ERROR: --display-width and --thumb-size must be positive integers.", file=sys.stderr)
        return 1

    print(f"Scanning: {input_dir}")
    items, unreadable_count = read_dicom_headers(input_dir)
    series_groups = group_series(items)
    study_count = len({item.study_uid for item in items})

    print(f"DICOM readable files: {len(items)}")
    print(f"Unreadable files: {unreadable_count}")
    print(f"Studies: {study_count}")
    print(f"Series: {len(series_groups)}")

    if not items:
        print("ERROR: no readable DICOM files found.", file=sys.stderr)
        return 1

    if args.list_series:
        list_series(series_groups)
        return 0

    try:
        include_indexes = parse_include_series(args.include_series, len(series_groups))
        series_labels = parse_series_labels(args.series_labels, len(series_groups))
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if include_indexes is None:
        selected_groups = list(enumerate(series_groups, start=1))
    else:
        selected_groups = [
            (index, group)
            for index, group in enumerate(series_groups, start=1)
            if index in include_indexes
        ]

    selected_studies = {group.study_uid for _, group in selected_groups}
    if len(selected_studies) != 1:
        print("ERROR: selected series must belong to a single StudyInstanceUID.", file=sys.stderr)
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        upload_dir, metadata = convert_series(
            selected_groups, output_dir, args.display_width, args.thumb_size, series_labels
        )
    except Exception as exc:
        print(f"ERROR: conversion failed: {exc}", file=sys.stderr)
        return 1

    print(f"Output: {upload_dir}")
    if args.zip:
        zip_path = output_dir / f"{upload_dir.name}.zip"
        zip_directory(upload_dir, zip_path)
        print(f"ZIP: {zip_path}")

    warning_count = len(metadata.get("warnings", []))
    print(f"Warnings: {warning_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
