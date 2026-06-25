from __future__ import annotations

import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RAW_ROOT = Path("data/raw")
PROCESSED_ROOT = Path("data/processed")
PROFILE_OUTPUT = PROCESSED_ROOT / "raw_data_profile.csv"
SUMMARY_OUTPUT = Path("docs/data_profile_summary.md")
EXPECTED_COLUMN_COUNT = 11
KNOWN_TRACE_TYPES = {"fastStorage", "Rnd"}
MONTH_FOLDER_PATTERN = re.compile(r"^\d{4}-\d{1,2}$")
DELIMITER_PATTERN = re.compile(r";\s*")


def discover_raw_files(raw_root: Path) -> list[Path]:
    """Return raw CSV files in deterministic order."""
    return sorted(raw_root.rglob("*.csv"))


def infer_trace_type(path: Path) -> str:
    for part in path.parts:
        if part in KNOWN_TRACE_TYPES:
            return part
    return "Unknown"


def infer_source_month_folder(path: Path) -> str:
    for part in path.parts:
        if MONTH_FOLDER_PATTERN.match(part):
            return part
    return "Unknown"


def clean_raw_line(line: str) -> str:
    cleaned = line.strip()
    if len(cleaned) >= 2 and cleaned.startswith('"') and cleaned.endswith('"'):
        return cleaned[1:-1]
    return cleaned


def split_trace_line(line: str) -> list[str]:
    cleaned = clean_raw_line(line)
    if not cleaned:
        return []
    return DELIMITER_PATTERN.split(cleaned)


def infer_timestamp_unit(value: float) -> str:
    if 1_000_000_000 <= value <= 2_000_000_000:
        return "seconds"
    if value >= 1_000_000_000_000:
        return "milliseconds"
    return "unknown"


def _convert_timestamp(value: float, unit: str) -> str:
    if unit == "seconds":
        converted = datetime.fromtimestamp(value, tz=timezone.utc)
    elif unit == "milliseconds":
        converted = datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    else:
        return ""
    return converted.replace(tzinfo=None).isoformat(sep=" ")


def _read_nonblank_lines(path: Path, limit: int = 20) -> list[str]:
    lines: list[str] = []
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        for line in handle:
            if line.strip():
                lines.append(line.rstrip("\r\n"))
            if len(lines) >= limit:
                break
    return lines


def profile_file(path: Path) -> dict[str, Any]:
    lines = _read_nonblank_lines(path)
    cleaned_lines = [clean_raw_line(line) for line in lines]
    parsed_lines = [split_trace_line(line) for line in lines]

    first_fields = parsed_lines[0] if parsed_lines else []
    has_header = bool(first_fields and "Timestamp" in first_fields[0])
    header_fields = first_fields if has_header else []
    data_fields = next((fields for idx, fields in enumerate(parsed_lines) if fields and not (idx == 0 and has_header)), [])

    timestamp_raw = data_fields[0] if data_fields else ""
    timestamp_unit = "unknown"
    converted_datetime = ""
    datetime_in_2013 = False
    timestamp_parse_error = ""
    if timestamp_raw:
        try:
            timestamp_value = float(timestamp_raw)
            timestamp_unit = infer_timestamp_unit(timestamp_value)
            converted_datetime = _convert_timestamp(timestamp_value, timestamp_unit)
            datetime_in_2013 = converted_datetime.startswith("2013-")
        except ValueError as exc:
            timestamp_parse_error = str(exc)

    wrapped_rows = [
        line.strip().startswith('"') and line.strip().endswith('"')
        for line in lines
        if line.strip()
    ]
    semicolon_lines = [bool(re.search(r";\s*", clean_raw_line(line))) for line in lines if line.strip()]
    delimiter_detected = bool(semicolon_lines and all(semicolon_lines))
    expected_counts = [
        len(fields) == EXPECTED_COLUMN_COUNT
        for fields in parsed_lines
        if fields
    ]

    return {
        "source_file": str(path),
        "trace_type": infer_trace_type(path),
        "source_month_folder": infer_source_month_folder(path),
        "sampled_line_count": len(lines),
        "rows_wrapped_in_double_quotes": bool(wrapped_rows and any(wrapped_rows)),
        "delimiter_detection_result": "semicolon_optional_whitespace" if delimiter_detected else "not_detected",
        "all_sampled_lines_have_semicolon_delimiter": delimiter_detected,
        "header_exists": has_header,
        "parsed_header_column_count": len(header_fields) if has_header else 0,
        "parsed_sample_data_column_count": len(data_fields),
        "sample_data_has_expected_columns": len(data_fields) == EXPECTED_COLUMN_COUNT,
        "header_has_expected_columns": (not has_header) or len(header_fields) == EXPECTED_COLUMN_COUNT,
        "timestamp_raw_value": timestamp_raw,
        "timestamp_unit_detection": timestamp_unit,
        "converted_sample_datetime": converted_datetime,
        "sample_datetime_in_2013": datetime_in_2013,
        "timestamp_parse_error": timestamp_parse_error,
        "parsed_header_fields_json": json.dumps(header_fields),
        "parsed_sample_row_json": json.dumps(data_fields),
        "cleaned_sample_lines_json": json.dumps(cleaned_lines[:3]),
        "all_sampled_nonblank_rows_have_expected_columns": bool(expected_counts and all(expected_counts)),
    }


def _write_profile(rows: list[dict[str, Any]]) -> None:
    PROCESSED_ROOT.mkdir(parents=True, exist_ok=True)
    if not rows:
        rows = [{"stop_condition_passed": False, "failure_reasons": "No profile rows generated"}]
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with PROFILE_OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _format_counter(counter: Counter[str]) -> str:
    if not counter:
        return "- None detected"
    return "\n".join(f"- {key}: {value}" for key, value in sorted(counter.items()))


def _write_summary(
    *,
    rows: list[dict[str, Any]],
    total_raw_csv_count: int,
    trace_type_counts: Counter[str],
    month_folder_counts: Counter[str],
    sample_count: int,
    stop_condition_passed: bool,
    failure_reasons: list[str],
) -> None:
    SUMMARY_OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    trace_types = ", ".join(sorted(trace_type_counts)) if trace_type_counts else "None"
    month_folders = ", ".join(sorted(month_folder_counts)) if month_folder_counts else "None"
    wrapped_values = sorted({str(row.get("rows_wrapped_in_double_quotes", "")) for row in rows})
    data_column_counts = sorted({str(row.get("parsed_sample_data_column_count", "")) for row in rows})
    timestamp_units = sorted({str(row.get("timestamp_unit_detection", "")) for row in rows})
    converted_datetimes = [str(row.get("converted_sample_datetime", "")) for row in rows]
    converted_datetimes = [value for value in converted_datetimes if value]
    only_faststorage_2013_8 = set(trace_type_counts) == {"fastStorage"} and set(month_folder_counts) == {"2013-8"}

    content = [
        "# Raw Data Profile Summary",
        "",
        "## Files Created",
        "",
        f"- `{PROFILE_OUTPUT.as_posix()}`",
        f"- `{SUMMARY_OUTPUT.as_posix()}`",
        "",
        "## Dataset Shape",
        "",
        f"- Total raw CSV count: {total_raw_csv_count}",
        f"- Sample files inspected: {sample_count}",
        f"- Detected trace types: {trace_types}",
        f"- Detected source month folders: {month_folders}",
        "",
        "### File Counts By Trace Type",
        "",
        _format_counter(trace_type_counts),
        "",
        "### File Counts By Source Month Folder",
        "",
        _format_counter(month_folder_counts),
        "",
        "## Parser Findings",
        "",
        f"- Rows wrapped in double quotes: {', '.join(wrapped_values) if wrapped_values else 'None sampled'}",
        "- Delimiter detection: semicolon with optional whitespace or tab after semicolons",
        f"- Parsed sample data column counts: {', '.join(data_column_counts) if data_column_counts else 'None'}",
        f"- Expected Bitbrains column count: {EXPECTED_COLUMN_COUNT}",
        "",
        "## Timestamp Findings",
        "",
        f"- Timestamp unit detection: {', '.join(timestamp_units) if timestamp_units else 'None'}",
        "- Converted sample datetimes:",
    ]
    content.extend(f"  - {value}" for value in converted_datetimes)
    if not converted_datetimes:
        content.append("  - None")
    content.extend(
        [
            f"- Sample datetimes in 2013: {all(bool(row.get('sample_datetime_in_2013')) for row in rows) if rows else False}",
            "",
            "## Stop Condition",
            "",
            f"- Stop condition passed: {stop_condition_passed}",
        ]
    )
    if failure_reasons:
        content.append("- Failure reasons:")
        content.extend(f"  - {reason}" for reason in failure_reasons)
    else:
        content.append("- Failure reasons: None")

    if only_faststorage_2013_8:
        content.extend(
            [
                "",
                "## Confirmed Limitation",
                "",
                "Only `fastStorage/2013-8` is present in the current raw extraction. No `Rnd` raw-data folder was detected during Stage 0 profiling.",
            ]
        )

    SUMMARY_OUTPUT.write_text("\n".join(content) + "\n", encoding="utf-8")


def _build_validation_failures(
    *,
    rows: list[dict[str, Any]],
    total_raw_csv_count: int,
    sample_count: int,
) -> list[str]:
    failures: list[str] = []
    if total_raw_csv_count <= 0:
        failures.append("No raw CSV files were found under data/raw.")
    if total_raw_csv_count >= 2 and sample_count < 2:
        failures.append("At least two sample files must be inspected when at least two raw CSV files exist.")
    if not rows:
        failures.append("No sample files were profiled.")
        return failures
    bad_data_rows = [
        row["source_file"]
        for row in rows
        if row.get("parsed_sample_data_column_count") != EXPECTED_COLUMN_COUNT
    ]
    if bad_data_rows:
        failures.append(f"Sampled data rows did not parse to {EXPECTED_COLUMN_COUNT} fields: {bad_data_rows}")
    bad_headers = [
        row["source_file"]
        for row in rows
        if row.get("header_exists") and row.get("parsed_header_column_count") != EXPECTED_COLUMN_COUNT
    ]
    if bad_headers:
        failures.append(f"Header rows did not parse to {EXPECTED_COLUMN_COUNT} fields: {bad_headers}")
    bad_sampled_rows = [
        row["source_file"]
        for row in rows
        if not row.get("all_sampled_nonblank_rows_have_expected_columns")
    ]
    if bad_sampled_rows:
        failures.append(f"One or more sampled nonblank rows did not parse to {EXPECTED_COLUMN_COUNT} fields: {bad_sampled_rows}")
    bad_timestamp_units = [
        row["source_file"]
        for row in rows
        if str(row.get("timestamp_raw_value", "")).startswith("1376314846")
        and row.get("timestamp_unit_detection") != "seconds"
    ]
    if bad_timestamp_units:
        failures.append("1376314846-style sample timestamp values were not detected as Unix seconds.")
    non_2013_dates = [
        row["source_file"]
        for row in rows
        if not row.get("sample_datetime_in_2013")
    ]
    if non_2013_dates:
        failures.append(f"Converted sample timestamps were not in 2013: {non_2013_dates}")
    return failures


def main() -> int:
    raw_files = discover_raw_files(RAW_ROOT)
    trace_type_counts = Counter(infer_trace_type(path) for path in raw_files)
    month_folder_counts = Counter(infer_source_month_folder(path) for path in raw_files)
    sample_files = raw_files[: min(2, len(raw_files))]

    profile_rows = [profile_file(path) for path in sample_files]
    failure_reasons = _build_validation_failures(
        rows=profile_rows,
        total_raw_csv_count=len(raw_files),
        sample_count=len(sample_files),
    )
    stop_condition_passed = not failure_reasons

    trace_counts_json = json.dumps(dict(sorted(trace_type_counts.items())))
    month_counts_json = json.dumps(dict(sorted(month_folder_counts.items())))
    sampled_files_json = json.dumps([str(path) for path in sample_files])
    for row in profile_rows:
        row.update(
            {
                "total_raw_csv_count": len(raw_files),
                "sampled_file_count": len(sample_files),
                "trace_type_counts_json": trace_counts_json,
                "source_month_folder_counts_json": month_counts_json,
                "sampled_source_files_json": sampled_files_json,
                "detected_trace_types": ", ".join(sorted(trace_type_counts)),
                "detected_source_month_folders": ", ".join(sorted(month_folder_counts)),
                "stop_condition_passed": stop_condition_passed,
                "failure_reasons": "; ".join(failure_reasons),
            }
        )

    if not profile_rows:
        profile_rows.append(
            {
                "total_raw_csv_count": len(raw_files),
                "sampled_file_count": 0,
                "trace_type_counts_json": trace_counts_json,
                "source_month_folder_counts_json": month_counts_json,
                "sampled_source_files_json": sampled_files_json,
                "stop_condition_passed": stop_condition_passed,
                "failure_reasons": "; ".join(failure_reasons),
            }
        )

    _write_profile(profile_rows)
    _write_summary(
        rows=profile_rows,
        total_raw_csv_count=len(raw_files),
        trace_type_counts=trace_type_counts,
        month_folder_counts=month_folder_counts,
        sample_count=len(sample_files),
        stop_condition_passed=stop_condition_passed,
        failure_reasons=failure_reasons,
    )

    if stop_condition_passed:
        print("Stage 0 raw data profiling stop condition passed.")
        print(f"Profile rows written: {len(profile_rows)}")
        print(f"Total raw CSV files: {len(raw_files)}")
        return 0

    print("Stage 0 raw data profiling stop condition failed.")
    for reason in failure_reasons:
        print(f"- {reason}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
