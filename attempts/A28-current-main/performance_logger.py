"""Sample system and checker CPU/RAM/GPU into one JSONL file; stdlib only."""

import argparse
import json
import math
import os
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path


def number(value):
    try:
        result = float(value.strip())
        return result if math.isfinite(result) else None
    except ValueError:
        return None


def cpu_times():
    values = list(map(int, Path("/proc/stat").read_text().splitlines()[0].split()[1:9]))
    return sum(values), values[3] + values[4], values[4]


def processes():
    result = {}
    for path in Path("/proc").iterdir():
        if not path.name.isdigit():
            continue
        try:
            fields = (path / "stat").read_text().rsplit(")", 1)[1].split()
            result[int(path.name)] = (
                int(fields[1]),
                int(fields[11]) + int(fields[12]),
                int(fields[19]),
                int(fields[21]),
            )
        except (OSError, ValueError, IndexError):
            continue  # A process can exit between listing and reading /proc.
    return result


def owned_pids(table, checker):
    found = {checker} if checker in table else set()
    while True:
        expanded = found | {pid for pid, row in table.items() if row[0] in found}
        if expanded == found:
            return found
        found = expanded


def gpu(owned):
    values = (
        subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,memory.total,power.draw,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            timeout=5,
        )
        .strip()
        .splitlines()
    )
    if len(values) != 1:
        raise ValueError("Expected the single-GPU VM")
    fields = values[0].split(",")
    if len(fields) != 5:
        raise ValueError("Unexpected GPU metric columns")
    metrics = dict(
        zip(
            ["gpu_util_pct", "gpu_mem_used_mib", "gpu_mem_total_mib", "gpu_power_w", "gpu_temp_c"],
            map(number, fields),
            strict=True,
        )
    )
    rows = (
        subprocess.check_output(
            [
                "nvidia-smi",
                "--query-compute-apps=pid,used_memory",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            timeout=5,
        )
        .strip()
        .splitlines()
    )
    metrics["gpu_processes"] = []
    for row in rows:
        pid, memory = row.split(",", 1)
        metrics["gpu_processes"].append(
            {"pid": int(pid), "memory_mib": number(memory), "belongs_to_checker": int(pid) in owned}
        )
    return metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--phase-file", type=Path, required=True)
    parser.add_argument("--stop-file", type=Path, required=True)
    parser.add_argument("--interval", type=float, default=2)
    parser.add_argument("--max-seconds", type=float, default=900)
    parser.add_argument("--append", action="store_true")
    args = parser.parse_args()
    if args.interval <= 0 or args.max_seconds <= 0:
        parser.error("Interval and maximum duration must be positive")
    os.umask(0o077)
    start = time.monotonic()
    previous_time, previous_cpu, previous_processes = None, None, {}
    peaks = {}
    samples = 0
    with args.out.open("a" if args.append else "x", buffering=1) as stream:

        def emit(row):
            stream.write(
                json.dumps({"utc": datetime.now(UTC).isoformat(), **row}, allow_nan=False) + "\n"
            )

        emit(
            {
                "kind": "start",
                "source_commit": "653b09c",
                "cpu_count": os.cpu_count(),
                "interval_s": args.interval,
                "scope": (
                    "System CPU is 0–100%; checker CPU uses 100% per core. "
                    "RSS is a sum, not unique RAM. GPU utilization is VM-wide; "
                    "per-process ownership is included. Cache policy is recorded by phase."
                ),
            }
        )
        while not args.stop_file.exists() and time.monotonic() - start < args.max_seconds:
            now = time.monotonic()
            row = {"kind": "sample", "elapsed_s": round(now - start, 3)}
            try:
                row["phase"] = args.phase_file.read_text().strip()[:100]
                checker = int((args.runtime / "checker.pid").read_text())
                row["checker_pid"] = checker
                cpu = cpu_times()
                row["system_cpu_pct"] = None
                row["system_iowait_pct"] = None
                if previous_cpu and cpu[0] > previous_cpu[0]:
                    delta = cpu[0] - previous_cpu[0]
                    row["system_cpu_pct"] = 100 * (1 - (cpu[1] - previous_cpu[1]) / delta)
                    row["system_iowait_pct"] = 100 * (cpu[2] - previous_cpu[2]) / delta
                table = processes()
                owned = owned_pids(table, checker)
                row["checker_processes"] = sorted(owned)
                row["checker_rss_sum_mib"] = (
                    sum(table[p][3] for p in owned) * os.sysconf("SC_PAGE_SIZE") / 1048576
                )
                new = [
                    p
                    for p in owned
                    if p not in previous_processes or previous_processes[p][2] != table[p][2]
                ]
                row["new_processes_without_cpu_interval"] = new
                row["checker_cpu_pct_per_core"] = None
                if previous_time is not None and not new:
                    ticks = sum(table[p][1] - previous_processes[p][1] for p in owned)
                    row["checker_cpu_pct_per_core"] = (
                        100 * ticks / os.sysconf("SC_CLK_TCK") / (now - previous_time)
                    )
                memory = {
                    line.split(":", 1)[0]: int(line.split()[1])
                    for line in Path("/proc/meminfo").read_text().splitlines()
                    if line.startswith(("MemTotal:", "MemAvailable:"))
                }
                row["system_ram_used_mib"] = (memory["MemTotal"] - memory["MemAvailable"]) / 1024
                row["system_ram_total_mib"] = memory["MemTotal"] / 1024
                row.update(gpu(owned))
                previous_time, previous_cpu, previous_processes = now, cpu, table
                for key, value in row.items():
                    if isinstance(value, (int, float)) and key not in {"checker_pid", "elapsed_s"}:
                        peaks[key] = max(peaks.get(key, value), value)
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                row["error"] = type(exc).__name__ + ": " + str(exc)[:200]
            emit(row)
            samples += 1
            time.sleep(args.interval)
        emit(
            {
                "kind": "summary",
                "samples": samples,
                "elapsed_s": time.monotonic() - start,
                "stop_reason": "requested" if args.stop_file.exists() else "time_limit",
                "maximum_observed": peaks,
            }
        )


if __name__ == "__main__":
    main()
