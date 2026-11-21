#!/usr/bin/env python3
"""Summarize a Game Performance Overview recording, weighted by presented frames."""

import argparse
import csv
import math
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict


FRAME_TABLE = "metal-perf-overview-layer-duration-metric"
THERMAL_TABLE = "device-thermal-state-intervals"


def table_rows(document, schema):
    """xctrace stores column names in the schema and reuses values via XML refs."""
    table = document.find(f".//schema[@name='{schema}']/..")
    if table is None:
        raise ValueError(f"Recording is missing {schema}")
    columns = [col.findtext("mnemonic") for col in table.findall("schema/col")]
    elements = {e.attrib["id"]: e for e in table.iter() if "id" in e.attrib}
    for row in table.findall("row"):
        if len(row) != len(columns):
            raise ValueError(f"Unexpected column count in {schema}")
        yield dict(zip(columns, (elements[e.attrib["ref"]] if "ref" in e.attrib else e
                                 for e in row)))


def summarize(frames, thermals, process, warmup):
    spans = [(int(r["start"].text), int(r["end"].text), r["thermal-state"].text)
             for r in table_rows(thermals, THERMAL_TABLE) if r["track-label"].text == "Current"]
    measurements = defaultdict(lambda: defaultdict(list))
    for r in table_rows(frames, FRAME_TABLE):
        if r["process-name"].text != process or r["metric-variant"].text != "0":
            continue
        metric = r["name"].get("fmt")
        start = int(r["start"].text)
        if metric not in ("Frame Interval", "GPU Active Time") or start < warmup * 1e9:
            continue
        end = start + int(r["duration"].text)
        state = "Unknown"
        for low, high, label in spans:
            if low <= start and end <= high:
                state = label
                break
            if low < end and start < high:
                state = "Partial or changing"
        count = int(r["number-of-frames"].text)
        if count > 0:
            value = float(r["value-in-ms"].text)
            if not math.isfinite(value) or value < 0 or (metric == "Frame Interval" and value == 0):
                raise ValueError(f"Invalid {metric} value {value}")
            key = (r["process"].get("fmt"), r["layer-id"].text, state)
            measurements[key][metric].append((count, value))

    result = []
    for (instance, layer, thermal), metrics in sorted(measurements.items()):
        intervals = metrics["Frame Interval"]
        if not intervals:
            continue
        n = sum(count for count, _ in intervals)
        mean = sum(count * value for count, value in intervals) / n
        gpu = metrics["GPU Active Time"]
        gpu_n = sum(count for count, _ in gpu)
        gpu_mean = sum(count * value for count, value in gpu) / gpu_n if gpu_n else None
        result.append((instance, layer, thermal, n, mean, 1000 / mean, gpu_n, gpu_mean))
    if not result:
        raise ValueError(f"No frame intervals for {process} after the warm-up")
    return result


def export_table(trace, schema):
    raw = subprocess.check_output([
        "xcrun", "xctrace", "export", "--input", trace, "--xpath",
        f"/trace-toc/run[@number='1']/data/table[@schema='{schema}']",
    ])
    return ET.fromstring(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", help="A single-run .trace from Game Performance Overview")
    parser.add_argument("--process", default="Tideways", help="Game executable name")
    parser.add_argument("--warmup", type=float, default=2.0, help="Seconds to exclude at trace start")
    args = parser.parse_args()
    if not math.isfinite(args.warmup) or args.warmup < 0:
        parser.error("warm-up must be a nonnegative finite number")
    try:
        rows = summarize(export_table(args.trace, FRAME_TABLE), export_table(args.trace, THERMAL_TABLE),
                         args.process, args.warmup)
    except (OSError, subprocess.CalledProcessError, ET.ParseError, KeyError, ValueError) as exc:
        parser.exit(1, f"Could not summarize recording: {exc}\n")
    writer = csv.writer(sys.stdout, lineterminator="\n")
    writer.writerow(["process", "layer", "thermal", "frames", "frame_ms", "fps", "gpu_frames", "gpu_active_ms"])
    for instance, layer, thermal, n, mean, fps, gpu_n, gpu_mean in rows:
        writer.writerow([instance, layer, thermal, n, f"{mean:.3f}", f"{fps:.2f}", gpu_n,
                         f"{gpu_mean:.3f}" if gpu_mean is not None else ""])


if __name__ == "__main__":
    main()
