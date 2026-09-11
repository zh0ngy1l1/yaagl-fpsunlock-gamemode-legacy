#!/usr/bin/env python3
"""Read-only production-log snapshots and post-run evidence checks.

This module never executes another program, reads process memory, mutates the
product, or infers stability/world entry from a successful FPS log message.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat


class EvidenceError(ValueError):
    pass


def require(value, message):
    if not value:
        raise EvidenceError(message)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def snapshot(path, output):
    """Exclusive snapshot of a stable regular file; never follows a log symlink."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        first = os.fstat(fd)
        require(stat.S_ISREG(first.st_mode), "Log is not a regular file")
        with os.fdopen(os.dup(fd), "rb") as stream:
            data = stream.read()
        last = os.fstat(fd)
        fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
        require(all(getattr(first, field) == getattr(last, field) for field in fields),
                "Log changed during snapshot")
        require(len(data) == last.st_size, "Short snapshot")
        current = os.lstat(path)
        require((current.st_dev, current.st_ino) == (last.st_dev, last.st_ino),
                "Log replaced during snapshot")
    finally:
        os.close(fd)
    out = Path(output)
    out.mkdir(mode=0o700)  # existing destinations fail; no replace/retry
    metadata = {"schema": 1, "source": os.path.abspath(path),
                "dev": last.st_dev, "ino": last.st_ino, "size": len(data),
                "mtime_ns": last.st_mtime_ns, "ctime_ns": last.st_ctime_ns,
                "sha256": sha256(data)}
    with (out / "log.bin").open("xb") as stream:
        stream.write(data)
    with (out / "snapshot.json").open("x") as stream:
        json.dump(metadata, stream, sort_keys=True, indent=2)
        stream.write("\n")
    return metadata


def load_snapshot(directory):
    directory = Path(directory)
    metadata = json.loads((directory / "snapshot.json").read_text())
    data = (directory / "log.bin").read_bytes()
    require(metadata["size"] == len(data) and metadata["sha256"] == sha256(data),
            "Snapshot identity mismatch")
    return metadata, data


def appended(before, after):
    old, prefix = before
    new, whole = after
    require(old["source"] == new["source"], "Different log paths")
    require((old["dev"], old["ino"]) == (new["dev"], new["ino"]), "Log inode changed")
    require(len(whole) > len(prefix), "No appended evidence or log truncated")
    require(whole.startswith(prefix), "Existing log prefix changed")
    require(not prefix or prefix.endswith(b"\n"), "Pre-run boundary splits a log line")
    require(whole.endswith(b"\n"), "Incomplete final log line")
    return whole[len(prefix):]


def exactly_one(lines, pattern, explanation):
    matches = [re.fullmatch(pattern, line) for line in lines]
    matches = [match for match in matches if match]
    require(len(matches) == 1, explanation)
    return matches[0]


def assess_release_log(before, after, *, target, wine, prefix, address=0x1452B4244):
    require(type(target) is int and 1 <= target <= 360, "Unsupported requested target")
    delta = appended(before, after)
    try:
        lines = delta.decode("utf-8", errors="strict").replace("\r\n", "\n").splitlines()
    except UnicodeError as error:
        raise EvidenceError("Log is not complete UTF-8") from error
    require(not any("diagnostic" in line.lower() or "automatic_gate" in line or
                    "ManualArm" in line for line in lines), "Diagnostic companion output present")
    require(not any("Another instance" in line for line in lines), "Duplicate companion")
    exactly_one(lines, r"----- .+ -----", "Expected exactly one new shell launch session")
    exactly_one(lines, re.escape("WINE=" + wine), "Selected Wine path missing or duplicated")
    prefix_lines = [line for line in lines if line.startswith("WINEPREFIX=")]
    require(prefix_lines and all(line == "WINEPREFIX=" + prefix for line in prefix_lines),
            "Selected prefix mismatch")  # frontend logs it twice (explicit + env)
    wine_lines = [line for line in lines if line.startswith("WINE=")]
    require(len(wine_lines) == 1, "Conflicting Wine assignment")
    dxmt_lines = [line for line in lines if line.startswith("DXMT_CONFIG=")]
    require(dxmt_lines == [f"DXMT_CONFIG=d3d11.preferredMaxFrameRate={target};"],
            "Companion renderer target differs")
    launch = exactly_one(lines, r"Starting unlockfps\.exe with target (\d+)\.\.\.",
                         "Expected one companion launch")
    headless = exactly_one(lines, r"Starting in headless mode with FPS limit: (-?\d+)",
                           "Expected one headless companion session")
    require(int(launch[1]) == target and int(headless[1]) == target, "Requested target mismatch")
    stamp = r"\[\d{2}:\d{2}:\d{2}\.\d{3}\] INFO GameInstanceService: "
    resolved = exactly_one(lines, stamp + r"Get FPS address successfully: (\d+)",
                           "Expected one resolved address")
    require(int(resolved[1]) == address, "Resolved address differs from pinned game")
    attached = exactly_one(lines, stamp + r"Find the game window: \[(0x[0-9A-Fa-f]+) ([^\]]+)\] \((\d+) GenshinImpact\.exe\) (.+)",
                           "Expected one Genshin attachment")
    require(int(attached[3]) > 0, "Invalid Windows PID")
    started = exactly_one(lines, stamp + r"Start applying FPS\.", "Missing or repeated apply loop")
    order = [lines.index(launch[0]), lines.index(headless[0]), lines.index(resolved[0]),
             lines.index(attached[0]), lines.index(started[0])]
    require(order == sorted(order) and len(set(order)) == len(order), "Invalid launch/attachment ordering")
    writes = []
    write_pattern = re.compile(stamp + r"FPS Override: (-?\d+) -> (-?\d+)")
    stop_positions = [i for i, line in enumerate(lines) if re.fullmatch(stamp + r"Stop applying FPS\.", line)]
    for index, line in enumerate(lines):
        if "FPS Override:" not in line:
            continue
        match = write_pattern.fullmatch(line)
        require(match is not None, "Unrecognized write evidence")
        require(index > order[-1], "Write precedes attachment/apply")
        require(not any(stop < index for stop in stop_positions), "Write after stopped apply loop")
        old, new = int(match[1]), int(match[2])
        require(-(2**31) <= old < 2**31, "Read value outside int32")
        require(new == target, "Write target mismatch")
        require(old != new, "Equality cannot produce this release write log")
        writes.append({"line": index + 1, "old": old, "target": new, "text": line})
    require(writes, "No successful complete-write evidence; write outcome inconclusive")
    require(len(stop_positions) <= 1, "Multiple apply stops")
    return {"profile": "ordinary-v3.0.7-source-supported-log", "target": target,
            "windows_pid_at_attachment": int(attached[3]), "window": attached[1],
            "address": hex(address), "writes": writes, "delta_sha256": sha256(delta),
            "delta_bytes": len(delta), "source_supported_complete_write": True,
            "limits": ["No sealed per-write PID binding, operation sequence or complete failed-operation journal",
                       "Log wall times are not atomic native-call times",
                       "Native host PID mapping requires independent corroboration; not established here",
                       "No world entry, gameplay duration, rendered FPS, harmlessness or stability assertion"]}


def assess_native(rows, *, expected_executable):
    require(len(rows) >= 4 and rows[0]["kind"] == "startup" and rows[-1]["kind"] == "footer",
            "Native observer startup/footer missing")
    require([row["sequence"] for row in rows] == list(range(1, len(rows) + 1)), "Native sequence gap")
    times = [row["monotonic_ns"] for row in rows]
    require(all(type(value) is int and value > 0 for value in times) and times == sorted(times),
            "Invalid native monotonic clock")
    require(rows[-1]["event_count_before_footer"] == len(rows) - 1, "Native footer count mismatch")
    require(rows[-1].get("production_processes_signaled") is False, "Observer contract differs")
    require(all(row.get("expected_native_executable") == expected_executable for row in rows),
            "Observer selected executable differs from reviewed product")
    observer_pids = {row.get("observer_pid") for row in rows}
    require(len(observer_pids) == 1 and next(iter(observer_pids)) > 0, "Observer PID identity changed")
    require(not any(row.get("foreground") and row["foreground"].get("pid") in observer_pids for row in rows),
            "Observer became foreground")
    require(sum(row["kind"] == "ready" for row in rows) == 1, "Native readiness ambiguous")
    heartbeats = [row["monotonic_ns"] for row in rows if row["kind"] == "heartbeat"]
    require(heartbeats and heartbeats[0] - times[0] <= 3_000_000_000 and
            times[-1] - heartbeats[-1] <= 3_000_000_000 and
            all(b - a <= 3_000_000_000 for a, b in zip(heartbeats, heartbeats[1:])),
            "Native heartbeat missing or gap exceeds three seconds")
    require(all(not row.get("state", {}).get("failures", []) for row in rows), "Native observer detected failure")
    bound = rows[-1]["state"]["bound"]
    require(bound and bound["pid"] > 0 and bound["launchDate"] and bound["executable"],
            "Incomplete native binding")
    require(bound["executable"] == expected_executable, "Bound host is not reviewed selected Wine")
    require(rows[-1]["state"]["integrity_ok"] is True and
            rows[-1]["state"]["complete_native_lifecycle"] is True and
            rows[-1]["state"]["selected_host_count"] == 1, "Native lifecycle incomplete or ambiguous")
    def same(item):
        return item and all(item.get(key) == bound[key] for key in ("pid", "launchDate", "executable"))
    # Independently check raw event ordering instead of trusting the footer summary.
    selected_activations = [i for i, row in enumerate(rows) if row["kind"] == "activate" and same(row.get("affected"))]
    departures = [i for i, row in enumerate(rows) if row["kind"] == "deactivate" and same(row.get("affected"))]
    exits = [i for i, row in enumerate(rows) if row["kind"] == "terminate" and same(row.get("affected"))]
    require(len(selected_activations) == 1 and len(exits) == 1 and len(departures) <= 1,
            "Native activation/departure/exit not singular")
    start, end = selected_activations[0], exits[0]
    require(start < end and (not departures or start < departures[0] <= end), "Native lifecycle ordering invalid")
    require(next(i for i, row in enumerate(rows) if row["kind"] == "ready") < start, "Observer not ready before game")
    finish = departures[0] if departures else end
    require(not any(row["kind"] == "activate" and not same(row.get("affected"))
                    for row in rows[start:finish]),
            "Other application activated during selected span")
    require(all(same(row.get("foreground")) for row in rows[start:finish]),
            "Native foreground differs during selected span")
    require(not any(row["kind"] == "startup" and same(row.get("affected")) for row in rows),
            "Selected host existed before observer")
    for row in rows:
        for item in (row.get("affected"), row.get("foreground")):
            require(not item or item.get("executable") != bound["executable"] or same(item),
                    "Second selected host or PID reuse")
    return {"native_host": bound, "first_activation_ns": times[start],
            "terminal_departure_ns": times[finish], "termination_ns": times[end],
            "observed_foreground_seconds": (times[finish] - times[start]) / 1e9,
            "integrity": "no detected failure; OS notification delivery completeness is not provable",
            "requires_video": "continuous world interval contained before the unique final game close/departure"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    take = sub.add_parser("snapshot")
    take.add_argument("log"); take.add_argument("output")
    assess = sub.add_parser("log")
    assess.add_argument("before"); assess.add_argument("after")
    assess.add_argument("--target", type=int, required=True)
    assess.add_argument("--wine", required=True); assess.add_argument("--prefix", required=True)
    native = sub.add_parser("native")
    native.add_argument("journal")
    native.add_argument("--wine-host", required=True)
    args = parser.parse_args()
    if args.command == "snapshot":
        result = snapshot(args.log, args.output)
    elif args.command == "log":
        result = assess_release_log(load_snapshot(args.before), load_snapshot(args.after),
                                    target=args.target, wine=args.wine, prefix=args.prefix)
    else:
        raw = Path(args.journal).read_bytes()
        require(raw.endswith(b"\n"), "Partial native footer")
        result = assess_native([json.loads(line) for line in raw.splitlines()], expected_executable=args.wine_host)
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
