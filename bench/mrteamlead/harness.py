# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Build the records programs in this folder and measure wall time and peak memory.

Runs on Windows, Linux and macOS. The measurement follows bench/run_bench.py and
scripts/toolchain.py of the Goose repository:

- peak memory is the peak working set on Windows (GetProcessMemoryInfo) and
  ru_maxrss from wait4 on Linux and macOS: the most physical memory the process
  held at one moment;
- time is the wall clock from spawning the process to its exit, so it includes
  process creation and teardown;
- the builds use the same settings: Rust with one codegen unit, Goose with the
  runtime compiled into the program (--standalone) at -O2.

The programs run in rounds, one run of each per round, so a change in background
load spreads over all of them instead of hitting one. The first rounds are
warm-up and are not recorded. Every program must print the same output as
records.rs; a program whose output differs is marked in the table.

The Goose compiler comes from the GOOSE environment variable, which names the
compiler or the folder of a Goose release; without it, goose from PATH.

Examples:
    GOOSE=/path/to/goose-v2026.3 uv run harness.py
    uv run harness.py --no-build --only records_workers.goose,records_fixed_workers.goose --chunk 16384
"""

from __future__ import annotations

import argparse
import io
import os
import platform
import re
import shutil
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "target"
OUTDIR = TARGET / "harness"
EXE = ".exe" if sys.platform == "win32" else ""
BASELINE = "records.rs"


@dataclass(frozen=True)
class Program:
    source: str              # file name in this folder, also the row label
    kind: str                # "rust" or "goose"
    chunked: bool = False    # takes the chunk size as its first argument

    @property
    def stem(self) -> str:
        return Path(self.source).stem

    @property
    def exe(self) -> Path:
        return TARGET / ("release" if self.kind == "rust" else "goose") / (self.stem + EXE)


PROGRAMS: list[Program] = [
    Program("records.rs", "rust"),
    Program("records_opt.rs", "rust"),
    Program("records_inline.rs", "rust"),
    Program("records_discriminant.rs", "rust"),
    Program("records_rayon.rs", "rust"),
    Program("records.goose", "goose"),
    Program("records_fixed.goose", "goose"),
    Program("records_workers.goose", "goose", chunked=True),
    Program("records_fixed_workers.goose", "goose", chunked=True),
]


@dataclass
class Run:
    ms: float
    peak: int                # bytes
    code: int


@dataclass
class Stats:
    program: Program
    times: list[float] = field(default_factory=list)
    peaks: list[int] = field(default_factory=list)
    output: str | None = None
    failure: str | None = None


# --- running one program -----------------------------------------------------

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    class _ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    _psapi = ctypes.WinDLL("psapi", use_last_error=True)

    def _peak_windows(handle: int) -> int:
        info = _ProcessMemoryCounters()
        info.cb = ctypes.sizeof(_ProcessMemoryCounters)
        ok: bool = bool(_psapi.GetProcessMemoryInfo(wintypes.HANDLE(handle), ctypes.byref(info), info.cb))
        if not ok:
            raise OSError(ctypes.get_last_error(), "GetProcessMemoryInfo failed")
        peak: int = int(info.PeakWorkingSetSize)
        return peak

    def run_once(argv: list[str], out: Path) -> Run:
        """One run; stdout and stderr go to `out`. The peak is read while Popen
        still holds the process handle: Windows reports nothing once it is closed."""
        with open(out, "wb") as fo:
            start = time.perf_counter()
            p = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=fo, stderr=subprocess.STDOUT)
            code = p.wait()
            ms = (time.perf_counter() - start) * 1000.0
            handle: int = int(getattr(p, "_handle"))
            return Run(ms, _peak_windows(handle), code)

else:

    def run_once(argv: list[str], out: Path) -> Run:
        """One run; stdout and stderr go to `out`. The process is spawned directly
        so that wait4 returns that one child's resource usage."""
        actions = [
            (os.POSIX_SPAWN_OPEN, 0, os.devnull, os.O_RDONLY, 0),
            (os.POSIX_SPAWN_OPEN, 1, str(out), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644),
            (os.POSIX_SPAWN_DUP2, 1, 2),
        ]
        start = time.perf_counter()
        pid = os.posix_spawn(argv[0], argv, os.environ, file_actions=actions)
        _, status, usage = os.wait4(pid, 0)
        ms = (time.perf_counter() - start) * 1000.0
        scale = 1 if sys.platform == "darwin" else 1024      # ru_maxrss: bytes on macOS, KB on Linux
        return Run(ms, usage.ru_maxrss * scale, os.waitstatus_to_exitcode(status))


# --- building ------------------------------------------------------------------

def run_tool(argv: list[str], env: dict[str, str] | None = None) -> str:
    """Run a build tool; on failure print what it said and stop."""
    r = subprocess.run(argv, cwd=HERE, env=env, capture_output=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(r.stdout + r.stderr, file=sys.stderr)
        sys.exit(f"failed: {' '.join(argv)}")
    return r.stdout + r.stderr


def native_path(p: str) -> str:
    """On Windows, a Git Bash or Cygwin path such as /c/Users/... as C:/Users/...;
    a shell passes environment variables to Python unconverted."""
    if sys.platform == "win32":
        m = re.match(r"^/(?:cygdrive/)?([A-Za-z])(/.*)?$", p)
        if m:
            return f"{m.group(1).upper()}:{m.group(2) or '/'}"
    return p


def find_goose() -> str:
    """The Goose compiler: $GOOSE, the compiler or the folder of a release, else goose from PATH."""
    given = os.environ.get("GOOSE", "")
    if not given:
        found = shutil.which("goose")
        if not found:
            sys.exit("goose not found: set GOOSE to the compiler or the folder of a Goose release, "
                     "or put goose on PATH")
        return str(Path(found).resolve())
    path = Path(native_path(given))
    if path.is_dir():                                   # the folder of a Goose release
        path = path / ("goose" + EXE)
    if not path.is_file() and Path(str(path) + EXE).is_file():
        path = Path(str(path) + EXE)
    if not path.is_file():
        sys.exit(f"no goose compiler at {path} (from GOOSE={given})")
    return str(path.resolve())


def build(programs: list[Program]) -> None:
    rust = [p for p in programs if p.kind == "rust"]
    if rust:
        # One codegen unit, as bench/run_bench.py builds Rust.
        env = dict(os.environ, CARGO_PROFILE_RELEASE_CODEGEN_UNITS="1")
        bins = [a for p in rust for a in ("--bin", p.stem)]
        print("cargo build --release (codegen-units=1)", file=sys.stderr)
        run_tool(["cargo", "build", "--release", "--manifest-path", str(HERE / "Cargo.toml"), *bins], env)
    gooses = [p for p in programs if p.kind == "goose"]
    if gooses:
        exe = find_goose()
        (TARGET / "goose").mkdir(parents=True, exist_ok=True)
        for p in gooses:
            print(f"goose build {p.source} --standalone", file=sys.stderr)
            run_tool([exe, "build", str(HERE / p.source), "--standalone", "-o", str(p.exe)])


# --- measuring -------------------------------------------------------------------

def measure(programs: list[Program], warmup: int, runs: int, chunk: int | None) -> list[Stats]:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    stats = [Stats(p) for p in programs]
    total = warmup + runs
    for r in range(total):
        print(f"\rround {r + 1}/{total}", end="", file=sys.stderr, flush=True)
        for s in stats:
            if s.failure:
                continue
            p = s.program
            if not p.exe.exists():
                s.failure = "not built"
                continue
            argv = [str(p.exe)] + ([str(chunk)] if p.chunked and chunk else [])
            out = OUTDIR / f"{p.source}.out"
            run = run_once(argv, out)
            if run.code != 0:
                s.failure = f"exit code {run.code}"
                continue
            if s.output is None:
                s.output = out.read_text(encoding="utf-8", errors="replace").strip()
            if r >= warmup:
                s.times.append(run.ms)
                s.peaks.append(run.peak)
    print(file=sys.stderr)
    return stats


# --- reporting -------------------------------------------------------------------

def table(header: list[str], rows: list[list[str]], right: list[bool]) -> str:
    """A Markdown table with aligned columns."""
    widths = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(header)]

    def line(cells: list[str]) -> str:
        return "| " + " | ".join(c.rjust(w) if rt else c.ljust(w)
                                 for c, w, rt in zip(cells, widths, right)) + " |"

    sep = "|" + "|".join("-" * (w + 1) + ":" if rt else "-" * (w + 2)
                         for w, rt in zip(widths, right)) + "|"
    return "\n".join([line(header), sep, *(line(r) for r in rows)])


def report(stats: list[Stats]) -> str:
    base = next((s for s in stats if s.program.source == BASELINE and s.times), None)
    ref = base.output if base else next((s.output for s in stats if s.output is not None), None)
    rows: list[list[str]] = []
    for s in stats:
        name = f"`{s.program.source}`"
        if s.failure or not s.times:
            rows.append([name, s.failure or "no runs", "", "", ""])
            continue
        if s.output != ref:
            name += " (output differs)"
        best = min(s.times)
        mean = statistics.mean(s.times)
        sd = statistics.stdev(s.times) if len(s.times) > 1 else 0.0
        speedup = f"{min(base.times) / best:.2f}x" if base else "--"
        rows.append([name, f"{best:.1f}", f"{mean:.1f} ± {sd:.1f}", speedup, f"{max(s.peaks) / 2**20:.1f}"])
    return table(["Program", "Min, ms", "Mean ± sd, ms", "Speedup", "Peak RAM, MB"], rows,
                 [False, True, True, True, True])


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", type=int, default=200, help="measured runs of each program (default 200)")
    ap.add_argument("--warmup", type=int, default=5, help="unrecorded rounds first (default 5)")
    ap.add_argument("--only", default="", help="comma-separated file names, e.g. records.rs,records.goose")
    ap.add_argument("--chunk", type=int, help="chunk size for the *_workers programs (default: their own)")
    ap.add_argument("--no-build", action="store_true", help="measure what is already built")
    args = ap.parse_args()
    runs: int = args.runs
    warmup: int = args.warmup
    only: list[str] = [s for s in str(args.only).split(",") if s]
    chunk: int | None = args.chunk
    no_build: bool = args.no_build

    unknown = [s for s in only if s not in {p.source for p in PROGRAMS}]
    if unknown:
        sys.exit(f"unknown programs: {', '.join(unknown)}")
    programs = [p for p in PROGRAMS if not only or p.source in only]
    if not no_build:
        build(programs)

    print(f"platform: {platform.platform()}, {platform.machine()}, {os.cpu_count()} logical CPUs")
    print(f"runs: {runs} measured after {warmup} warm-up rounds"
          + (f", chunk {chunk}" if chunk else ""))
    print()
    print(report(measure(programs, warmup, runs, chunk)))


if __name__ == "__main__":
    main()
