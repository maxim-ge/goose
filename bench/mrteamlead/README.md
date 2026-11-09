# MrTeamlead: step-by-step optimization of records.rs

- Source: MrTeamlead's video "[18 минут ЧИСТЕЙШЕГО БЛЭЙЗИНГА в истории программирования](https://www.youtube.com/watch?v=6n-yl2Qolvg)" ("18 minutes of the purest blazing in programming history")
- Base: `bench/rust/records.rs`, commit `963a7981`
- Branch: `mrteamlead`
- Steps 1–2 as a diff of the author's `bench/rust/records.rs` itself: branch [`mrteamlead-diff-1-2`](https://github.com/maxim-ge/goose/compare/963a7981...mrteamlead-diff-1-2), one commit per step

## Results

| Program                       | Steps                          | Min. time | Speedup | Peak RAM |   Video | Video speedup |
|-------------------------------|--------------------------------|----------:|--------:|---------:|--------:|--------------:|
| `records.rs`                  | original code                  |  131.2 ms |   1.00x |  78.3 MB | 64.1 ms |         1.00x |
| `records_opt.rs`              | 1–2                            |   74.7 ms |   1.76x |  50.7 MB | 46.7 ms |         1.37x |
| `records_inline.rs`           | 1–3                            |   75.3 ms |   1.74x |  50.8 MB | 45.9 ms |         1.40x |
| `records_discriminant.rs`     | 1–4                            |   76.4 ms |   1.72x |  50.7 MB | 41.3 ms |         1.55x |
| `records_rayon.rs`            | 1–4 + rayon, reconstruction    |   40.5 ms |   3.24x |  51.9 MB |  9.5 ms |         6.75x |
| `records.goose`               | Goose, variable enum           |   68.0 ms |   1.93x |  22.7 MB |      -- |            -- |
| `records_fixed.goose`         | Goose, fixed enum              |   80.1 ms |   1.64x |  45.1 MB | 46.5 ms |         1.38x |
| `records_workers.goose`       | Goose, variable enum + workers |   75.8 ms |   1.73x |  23.5 MB |      -- |            -- |
| `records_fixed_workers.goose` | Goose, fixed enum + workers    |   51.1 ms |   2.57x |  48.0 MB |      -- |            -- |

- Measured by `harness.py`: the minimum time and the maximum peak RAM over the runs
- Preliminary: 5 runs after 1 warm-up round, 2026-11-09
- Video: the rayon time is for the author's `record_fx` + rayon version, whose code is not shown

## Environment

- Machine: Acer Veriton S2690G
- CPU: Intel Core i7-12700, 8P + 4E cores, 20 threads, 2.1 GHz
- RAM: 32 GB, 2 × 16 GB, 2400 MT/s
- OS: Windows 11 Pro 10.0.26200, Balanced power plan
- Rust: rustc 1.98.1 (48a229cea 2026-09-01), cargo 1.98.1
- Goose: v2026.3 release for Windows x64, C compiler MSVC 19.44.35229 (Visual Studio Build Tools 2022)
- Build and measurement: `GOOSE=<path to goose> uv run harness.py`, see [harness.py](#harnesspy)

## Environment in the video

- Platform: macOS arm64 (`goose-v2026.3-macos-arm64`)
- Build: `cargo build --release`
- Benchmark: `hyperfine --warmup=100`

## Files

- Parameters in all programs: `N` = 2,000,000, `PASSES` = 4
- Output of all programs: `2000000`, `350419807120`

### records.rs

- The original code
- `N` changed from 500,000 to 2,000,000

### records_opt.rs

- Steps 1–2, based on `records.rs`
- Step 1: `Vec::with_capacity(N)` -- [05:00](https://www.youtube.com/watch?v=6n-yl2Qolvg&t=300s)
- Step 2: `String` → `#[derive(Clone, Copy)] struct MyString { bytes: [u8; 15], len: u8 }` -- [06:27](https://www.youtube.com/watch?v=6n-yl2Qolvg&t=387s)

### records_inline.rs

- Steps 1–3, based on `records_opt.rs`
- Step 3: `#[inline(always)] fn score(e: Event) -> i64`, `#[derive(Clone, Copy)]` on `Event`, passes through `chunks_exact(4)` -- [09:35](https://www.youtube.com/watch?v=6n-yl2Qolvg&t=575s), [10:42](https://www.youtube.com/watch?v=6n-yl2Qolvg&t=642s)

### records_discriminant.rs

- Steps 1–4, based on `records_inline.rs`
- Step 4: `#[repr(u8)]` on `enum Event`, the `Tick` variant moved to the end -- [12:57](https://www.youtube.com/watch?v=6n-yl2Qolvg&t=777s)

### records_rayon.rs

- Steps 1–4 + rayon, based on `records_discriminant.rs` -- [16:07](https://www.youtube.com/watch?v=6n-yl2Qolvg&t=967s)
- Reconstruction: the video runs a prebuilt binary and does not show its code
- Each pass sums the events in parallel (`par_iter`), generation stays sequential

### records.goose

- Copy of `bench/goose/records_var.goose`, Goose's own `records` benchmark
- Variable-mode enum: each event takes the size of its own variant, the text inline behind a varint length
- The video ran `records_fixed.goose` instead

### records_fixed.goose

- Copy of `bench/goose/records_fixed.goose`: the same log in the fixed-mode enum, every event sized for the largest variant, the text in an inline `u8[..15]`
- The same layout as `records_opt.rs` (step 2)
- The Goose program the video ran: 46.5 ms -- [09:07](https://www.youtube.com/watch?v=6n-yl2Qolvg&t=547s)

### records_workers.goose

- `records.goose` with the passes spread over worker threads
- Goose threads share no memory, so `main` sends the log to the workers through a typed queue in chunks; each worker runs all passes over a chunk and sends back its sum
- A log of variable-size events cannot be indexed or sliced, so `main` walks it and copies each chunk's events into a buffer before sending it
- At most two chunks per worker are in flight, so the copies take little memory beyond the log
- Usage: `records_workers [chunk]`, events per chunk, 4096 by default
- Slower than `records.goose`: `main` copies for about 56 ms, while the passes it hands off take about 40 ms
  - walking the log: about 5 ms
  - copying each event into the buffer (`push(copy(e))`): about 17 ms
  - copying the buffer into the message (`copy(buf)`): about 19 ms
  - `qput`: about 15 ms
  - measured inside `main` with `clock()`, chunk 4096, Goose v2026.3
- Keeping the log as a list of chunks from the start, so that a chunk is sent without the walk, was slower still: 73.8 ms

### records_fixed_workers.goose

- Goose counterpart of `records_rayon.rs`: `records_fixed.goose` with the passes spread over worker threads
- A log of fixed-size events can be sliced, so `main` sends each chunk as one copy, `log[a..b]`, through a typed queue
- Each worker runs all passes over a chunk and sends back its sum; at most two chunks per worker are in flight, so the copies take little memory beyond the log
- Usage: `records_fixed_workers [chunk]`, events per chunk, 4096 by default

### records.c

- `records.goose` transpiled to C, `goose -O2 --standalone -o records.c records.goose`: the runtime is included, so it builds on its own with any C compiler
- Not built by `harness.py`
- The same C with three compilers, best of 100 runs with hyperfine, 2026-11-09
  - gcc 12.2.0 (MinGW-w64), `-O2`: 58.0 ms
  - clang 19.1.5 (bundled with Visual Studio Build Tools), `-O2`: 67.1 ms
  - MSVC 19.44, `/O2`, which `goose build` uses on this machine: 67.7 ms
- Building the log takes the same with all three, about 28 ms; the difference is in the passes, in how each compiler dispatches on the event tag
  - gcc: a short compare chain
  - clang: a jump table, one indirect jump per event
  - MSVC: a compare chain that tests the rarest tag first
- clang with `-fno-jump-tables`: 62.1 ms, against 67.0 ms with jump tables and 57.5 ms for gcc in the same session

### harness.py

- Builds and measures all the programs above; runs on Windows, Linux and macOS with Python 3.11 or later, no dependencies
- Builds with the settings of the Goose repository's `bench/run_bench.py`
  - Rust: `cargo build --release` with one codegen unit
  - Goose: `goose build --standalone` (runtime compiled into the program, `-O2` by default) into `target/goose/`
- Measures each run as `scripts/toolchain.py` does
  - time: wall clock from spawning the process to its exit
  - peak RAM: peak working set on Windows (`GetProcessMemoryInfo`), `ru_maxrss` on Linux and macOS
- Runs the programs in rounds, one run of each per round, after unrecorded warm-up rounds
- Checks that every program prints the same output as `records.rs`
- Prints a Markdown table: minimum time, mean ± sd, speedup over `records.rs`, maximum peak RAM
- The Goose compiler: `GOOSE`, the compiler or the folder of a Goose release, as in `layout/run.sh`; without it, `goose` from `PATH`
- Options
  - `--runs N` -- measured runs of each program, 200 by default
  - `--warmup N` -- warm-up rounds, 5 by default
  - `--only a.rs,b.goose` -- measure only these files
  - `--chunk N` -- chunk size for the `*_workers.goose` programs
  - `--no-build` -- measure what is already built
- Example: `uv run harness.py --no-build --only records_workers.goose,records_fixed_workers.goose --chunk 16384`

### layout/

- Checks the table in section 8 of the Goose tutorial, "Nested data stays inline": the bytes and heap allocations of one order in Goose, C++ and Rust
- See [layout/README.md](layout/README.md)

### bench.rs

- Copy of `bench/rust/bench.rs`: `xs_next`, `xs_mod`, `emit`

### rng.goose

- Copy of `bench/goose/rng.goose`: `xs_next`, `xs_mod`

### Cargo.toml, Cargo.lock

- Five binaries, one per `records*.rs` file
- Dependency: rayon 1.12.0
