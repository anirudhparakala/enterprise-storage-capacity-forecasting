from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "src" / "01_ingest_bitbrains.py"


def load_ingest_module():
    if not MODULE_PATH.exists():
        pytest.fail("Stage 1 implementation module is missing")
    spec = importlib.util.spec_from_file_location("stage_1_ingest_bitbrains", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_trace(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_parse_trace_file_parses_semicolon_rows_and_seconds_timestamps(tmp_path: Path) -> None:
    module = load_ingest_module()
    raw_root = tmp_path / "raw"
    trace_path = raw_root / "fastStorage" / "2013-8" / "1.csv"
    write_trace(
        trace_path,
        [
            "Timestamp [ms];\tCPU cores;\tCPU capacity provisioned [MHZ];\tCPU usage [MHZ];\tCPU usage [%];\tMemory capacity provisioned [KB];\tMemory usage [KB];\tDisk read throughput [KB/s];\tDisk write throughput [KB/s];\tNetwork received throughput [KB/s];\tNetwork transmitted throughput [KB/s]",
            "1376314846;\t4;\t11703.99824;\t10912.027692426667;\t93.23333333333333;\t6.7108864E7;\t6129274.4;\t0.13333333333333333;\t15981.6;\t0.0;\t2.1333333333333333",
        ],
    )

    df, summary = module.parse_trace_file(trace_path, raw_root)

    assert summary["accepted_rows"] == 1
    assert summary["failed_rows"] == 0
    assert list(df.columns) == module.TARGET_COLUMNS
    row = df.iloc[0]
    assert row["source_file"] == str(trace_path)
    assert row["trace_type"] == "fastStorage"
    assert row["source_month_folder"] == "2013-8"
    assert row["vm_id"] == "fastStorage_2013-8_1"
    assert row["timestamp_unit_detected"] == "seconds"
    assert row["datetime"] == pd.Timestamp("2013-08-12 13:40:46")
    assert row["date"] == "2013-08-12"
    assert row["month"] == "2013-08-01"
    assert row["hour"] == 13
    assert pd.api.types.is_numeric_dtype(df["disk_write_kbps"])


def test_parse_trace_file_strips_outer_quotes_and_detects_milliseconds(tmp_path: Path) -> None:
    module = load_ingest_module()
    raw_root = tmp_path / "raw"
    trace_path = raw_root / "Rnd" / "2013-10" / "vm.alpha.csv"
    write_trace(
        trace_path,
        [
            '"1376314846000; 2; 2000; 100; 5; 4096; 2048; 1; 2; 3; 4"',
        ],
    )

    df, summary = module.parse_trace_file(trace_path, raw_root)

    assert summary["accepted_rows"] == 1
    assert summary["failed_rows"] == 0
    assert df.loc[0, "trace_type"] == "Rnd"
    assert df.loc[0, "source_month_folder"] == "2013-10"
    assert df.loc[0, "vm_id"] == "Rnd_2013-10_vm_alpha"
    assert df.loc[0, "timestamp_unit_detected"] == "milliseconds"
    assert df.loc[0, "datetime"] == pd.Timestamp("2013-08-12 13:40:46")


def test_parse_trace_file_counts_malformed_and_unknown_timestamp_rows(tmp_path: Path) -> None:
    module = load_ingest_module()
    raw_root = tmp_path / "raw"
    trace_path = raw_root / "fastStorage" / "2013-8" / "bad.csv"
    write_trace(
        trace_path,
        [
            "Timestamp [ms]; CPU cores; CPU capacity provisioned [MHZ]; CPU usage [MHZ]; CPU usage [%]; Memory capacity provisioned [KB]; Memory usage [KB]; Disk read throughput [KB/s]; Disk write throughput [KB/s]; Network received throughput [KB/s]; Network transmitted throughput [KB/s]",
            "",
            "not-a-timestamp; 4; 1; 1; 1; 1; 1; 1; 1; 1; 1",
            "12345; 4; 1; 1; 1; 1; 1; 1; 1; 1; 1",
            "1376314846,4,1,1,1,1,1,1,1,1,1",
            "1376314846; 4; 1; 1; 1; 1; 1; 1; 1; 1; 1",
        ],
    )

    df, summary = module.parse_trace_file(trace_path, raw_root)

    assert len(df) == 1
    assert summary["data_rows_seen"] == 4
    assert summary["accepted_rows"] == 1
    assert summary["failed_rows"] == 3


def test_validate_ingested_rejects_unknown_metadata_and_bad_column_order() -> None:
    module = load_ingest_module()
    row = {column: 1 for column in module.TARGET_COLUMNS}
    row.update(
        {
            "source_file": "raw/other/1.csv",
            "source_month_folder": "Unknown",
            "trace_type": "Unknown",
            "vm_id": "other_1",
            "timestamp_raw": 1376314846,
            "timestamp_unit_detected": "seconds",
            "datetime": pd.Timestamp("2013-08-12 13:40:46"),
            "date": "2013-08-12",
            "month": "2013-08-01",
            "hour": 13,
        }
    )
    df = pd.DataFrame([row], columns=module.TARGET_COLUMNS)

    with pytest.raises(ValueError, match="Unknown"):
        module.validate_ingested(df, pd.DataFrame(), failed_parse_rate=0.0)

    with pytest.raises(ValueError, match="column order"):
        module.validate_ingested(df[module.TARGET_COLUMNS[::-1]], pd.DataFrame(), failed_parse_rate=0.0)
