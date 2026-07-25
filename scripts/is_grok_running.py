#!/usr/bin/env python3
"""Detect whether a Grok / complete_apply job-apply process is already running.

Exit codes:
  0 = grok/apply IS running (skip starting another apply)
  1 = not running (safe to check-in + apply)
  2 = hard error

Also writes github outputs when GITHUB_OUTPUT is set:
  running=true|false
  reason=...
"""
from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

PROCESS_HINTS = (
    "grok_apply_with_report",
    "complete_apply.py",
    "complete_apply",
    "strategy_sectors",
    "apply_once_each",
)

LOCK_NAMES = (
    ".cdp_apply.lock",
    ".cdp_apply_chrome.lock",
    ".cdp_apply_chromium.lock",
    ".grok_apply_running",
)

STALE_LOCK_SEC = int(os.environ.get("CDP_LOCK_STALE_SEC", "7200"))


def _workdir() -> Path:
    env = (os.environ.get("JOB_APPLY_WORKDIR") or "").strip()
    if env:
        return Path(env).expanduser().resolve()
    candidates = [
        Path.home() / "job-application-bot" / "data" / "etoro-apply-report",
        Path.home() / "deepline" / "data" / "karlsruhe-public-co-job-apps",
        Path.cwd(),
    ]
    for c in candidates:
        if c.is_dir():
            return c.resolve()
    return Path.cwd()


def _set_output(key: str, value: str) -> None:
    out = os.environ.get("GITHUB_OUTPUT")
    if not out:
        return
    with open(out, "a", encoding="utf-8") as f:
        f.write(f"{key}={value}\n")


def lock_held(workdir: Path) -> tuple[bool, str]:
    for name in LOCK_NAMES:
        p = workdir / name
        if not p.is_file():
            # also check grok repo src next to workdir scripts
            continue
        try:
            age = time.time() - p.stat().st_mtime
        except OSError:
            continue
        if age < STALE_LOCK_SEC:
            return True, f"lock file {name} age={int(age)}s"
        try:
            p.unlink()
        except OSError:
            pass
    # search common sibling locations for lock
    for base in (workdir, workdir.parent, Path.cwd()):
        for name in LOCK_NAMES:
            p = base / name
            if p.is_file():
                try:
                    age = time.time() - p.stat().st_mtime
                except OSError:
                    continue
                if age < STALE_LOCK_SEC:
                    return True, f"lock file {p} age={int(age)}s"
    return False, ""


def process_running() -> tuple[bool, str]:
    """Best-effort process scan (Windows + Unix)."""
    try:
        import psutil  # type: ignore

        me = os.getpid()
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            if proc.info.get("pid") == me:
                continue
            cmd = " ".join(proc.info.get("cmdline") or [])
            low = cmd.lower()
            for hint in PROCESS_HINTS:
                if hint.lower() in low:
                    return True, f"pid={proc.info.get('pid')} cmd contains {hint}"
        return False, ""
    except Exception:
        pass

    # Fallback: Windows tasklist / wmic-ish via powershell is heavy; try /proc
    if sys.platform.startswith("linux") or sys.platform == "darwin":
        proc = Path("/proc")
        if proc.is_dir():
            for d in proc.iterdir():
                if not d.name.isdigit():
                    continue
                try:
                    cmd = (d / "cmdline").read_bytes().replace(b"\x00", b" ").decode(
                        "utf-8", "replace"
                    )
                except Exception:
                    continue
                low = cmd.lower()
                for hint in PROCESS_HINTS:
                    if hint.lower() in low and str(os.getpid()) not in d.name:
                        return True, f"pid={d.name} cmd contains {hint}"
        return False, ""

    # Windows fallback without psutil: tasklist + findstr via wmic
    if os.name == "nt":
        try:
            import subprocess

            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-CimInstance Win32_Process | Select-Object -ExpandProperty CommandLine"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            blob = (r.stdout or "").lower()
            for hint in PROCESS_HINTS:
                if hint.lower() in blob:
                    return True, f"windows process list contains {hint}"
        except Exception as e:
            return False, f"process scan failed: {e}"
    return False, ""


def main() -> int:
    workdir = _workdir()
    print(f"workdir={workdir}")

    held, why = lock_held(workdir)
    if held:
        print(f"RUNNING: {why}")
        _set_output("running", "true")
        _set_output("reason", why.replace("\n", " ")[:200])
        return 0

    running, why = process_running()
    if running:
        print(f"RUNNING: {why}")
        _set_output("running", "true")
        _set_output("reason", why.replace("\n", " ")[:200])
        return 0

    print("NOT_RUNNING: no lock and no apply process")
    _set_output("running", "false")
    _set_output("reason", "idle")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
