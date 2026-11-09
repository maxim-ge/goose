# Layout: nested data stays inline

Checks the table in the Goose tutorial, [section 8, "Nested data stays inline"](https://github.com/maxim-ge/goose/blob/963a79811c241928a296d3036f18d5be4c896c69/docs/tutorial.md#8-nested-data-stays-inline) (commit `963a7981`): one order takes 29 bytes and 0 allocations in Goose, 160 bytes and 1 allocation in C++, 153 bytes and 4 allocations in Rust.

## Method

The order, as JSON:

```json
{
  "id": 1001,
  "customer": "alice",
  "items": [
    { "sku": "SKU-441", "qty": 2, "cents": 1999 },
    { "sku": "SKU-7", "qty": 1, "cents": 500 }
  ]
}
```

- Size, counted as the tutorial counts: the order itself plus the heap blocks it owns, at their requested sizes, without the allocator's own header and rounding
  - Goose, [order.goose](order.goose): the tutorial's code unchanged; `bytes_of(book)` after one push is the order's bytes
  - C++, [order.cpp](order.cpp): `sizeof(Order)` plus the blocks counted by a replaced global `operator new` / `operator delete`
  - Rust, [order.rs](order.rs): `size_of::<Order>()` plus the blocks counted by a `#[global_allocator]`
- Goose allocations: Goose has no allocator to replace, so the heap calls of the whole process are counted
  - The program is transpiled to C and linked with [count_malloc.c](count_malloc.c), which counts every `malloc`, `calloc` and `realloc` through gcc's `-Wl,--wrap`
  - [order_empty.goose](order_empty.goose), the same program without the order, gives the runtime's own count; the difference is what the order allocates
  - A separate program rather than a command-line switch, because reading the command line costs a heap call of its own
- Cases beyond the tutorial's
  - C++: a SKU one character longer, and SKUs of 16 characters
  - Rust: `collect` as written, and exact capacity through `shrink_to_fit()`
- The Goose program at the C level: [order.goose.c](order.goose.c), `order.goose` transpiled by `goose -O2 --standalone`; most of the file is the runtime, the program is at the end, from `main_g` on line 4102
- [order.goose.rs](order.goose.rs): a copy of `order.goose` with the `.rs` extension, only so that GitHub highlights its syntax
- [run.sh](run.sh) builds and runs everything; the output of the last run is [results.md](results.md)

## Findings

- Goose, 29 bytes and 0 allocations: confirmed; the runtime makes the same number of heap calls with the order and without it
- C++, 160 bytes and 1 allocation: confirmed, with MSVC and g++; building the order takes 2 allocation calls, as the vector grows from 1 to 2 items
- Rust, 153 bytes and 4 allocations: only at exact capacity; `collect` gives the items array capacity 4, and the order takes 233 bytes
- Two claims in the text do not hold
  - "With one more character in a SKU, C++ would need four allocations too": MSVC and libstdc++ keep strings of up to 15 characters inside `std::string`, so it stays one block; 16-character SKUs give three, as `alice` stays inline
  - "`id`, `qty` and `cents` take one byte each rather than eight": a `varint` field is zigzag-encoded, which doubles the value, so only `qty` takes one byte; `id` 1001 and both `cents` take two

The 29 Goose bytes:

- `d2 0f` -- `id` 1001
- `05 61 6c 69 63 65` -- `customer`: the length, then `alice`
- `02` -- the number of items
- `07 53 4b 55 2d 34 34 31` `04` `9e 1f` -- `SKU-441`, qty 2, cents 1999
- `05 53 4b 55 2d 37` `02` `e8 07` -- `SKU-7`, qty 1, cents 500

## Running

```bash
GOOSE=/path/to/goose ./run.sh > results.md   # the compiler or the folder of a Goose release; from PATH if unset
```

- Prints Markdown, a section per step; the builds go to `../target/layout/`
- Steps: Goose; the Goose heap calls; C++ with g++ and with MSVC; Rust; a step whose tool is missing is skipped
- The heap count needs gcc with a linker that has `--wrap`, which the macOS one lacks
- MSVC: Windows only, from `PATH` or through the Visual Studio install that `vswhere` finds
- Tested on Windows only

## Environment

- Windows 11 Pro 10.0.26200, x64, 2026-11-09
- Goose v2026.3, `goose build` with MSVC 19.44.35229
- MSVC 19.44.35229 (Visual Studio Build Tools 2022), g++ and gcc 12.2.0 (MinGW-w64), rustc 1.98.1
