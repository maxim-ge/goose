#!/usr/bin/env bash
# Builds and runs the layout examples: Goose, the heap calls of the Goose
# program, C++ with g++ and with MSVC, and Rust. Prints the results as
# Markdown, a section per step; the builds go to ../target/layout/. A step
# whose tool is missing is skipped.
#
# Usage:
#   ./run.sh                          goose from PATH
#   GOOSE=/path/to/goose ./run.sh     the compiler, or the folder that holds it
#   ./run.sh > results.md             the results as a Markdown file
set -euo pipefail

goose="${GOOSE:-$(command -v goose || true)}"
if [ -n "$goose" ]; then
    if [ -d "$goose" ]; then              # the folder of a Goose release
        goose="${goose%/}/goose"
    fi
    if [ ! -f "$goose" ] && [ -f "$goose.exe" ]; then
        goose="$goose.exe"
    fi
    if [ ! -f "$goose" ]; then
        printf 'run.sh: no goose compiler at %s (from GOOSE=%s)\n' "$goose" "${GOOSE:-}" >&2
        exit 1
    fi
    goose="$(cd "$(dirname "$goose")" && pwd)/$(basename "$goose")"   # absolute, before the cd below
fi

cd "$(dirname "$0")"
out=../target/layout
mkdir -p "$out"

exe=""
windows=false
case "$(uname -s)" in
    MINGW* | MSYS* | CYGWIN*) exe=".exe"; windows=true ;;
esac

have() { command -v "$1" >/dev/null 2>&1; }
step() { printf '\n## %s\n\n' "$1"; }
skip() { step "$1"; printf -- '- skipped: %s\n' "$2"; }

# Runs a build command quietly; on failure prints what it said, to stderr.
quiet() {
    local log
    if ! log="$("$@" 2>&1)"; then
        printf '%s\n' "$log" >&2
        return 1
    fi
}

printf '# Layout: results\n'

# 1. Goose
if [ -n "$goose" ]; then
    step "Goose"
    quiet "$goose" build order.goose -o "$out/order_goose$exe"
    "$out/order_goose$exe"
else
    skip "Goose" "set GOOSE or put goose on PATH"
fi

# 2. The heap calls of the Goose program: the order, then the baseline without it
if [ -n "$goose" ] && have gcc; then
    step "Goose heap calls"
    counts=()
    for f in order order_empty; do
        quiet "$goose" -O2 --standalone -o "$out/$f.c" "$f.goose"
        if quiet gcc -O2 "$out/$f.c" count_malloc.c -Wl,--wrap=malloc,--wrap=calloc,--wrap=realloc \
                -o "$out/${f}_counted$exe"; then
            n="$("$out/${f}_counted$exe" 2>&1 >/dev/null | sed -n 's/^heap calls: //p' | tr -d '\r')"
            counts+=("$n")
            printf -- '- `%s.goose`: %s\n' "$f" "$n"
        else
            printf -- '- `%s.goose`: skipped, the linker does not support --wrap\n' "$f"
        fi
    done
    if [ "${#counts[@]}" -eq 2 ]; then
        printf -- '- added by the order: %s\n' "$((counts[0] - counts[1]))"
    fi
else
    skip "Goose heap calls" "needs goose and gcc"
fi

# 3. C++ with g++
if have g++; then
    step "C++, g++"
    static=()
    if $windows; then static=(-static); fi    # else the MinGW C++ runtime DLLs must be on PATH
    quiet g++ -O2 -std=c++17 "${static[@]}" order.cpp -o "$out/order_cpp_gcc$exe"
    "$out/order_cpp_gcc$exe"
else
    skip "C++, g++" "g++ not found"
fi

# 4. C++ with MSVC, Windows only: cl from PATH, else through vcvars64.bat found by vswhere
msvc_args=(/nologo /O2 /EHsc /std:c++17 order.cpp '/Fe..\target\layout\order_cpp.exe' '/Fo..\target\layout\')
if $windows && have cl; then
    step "C++, MSVC"
    MSYS_NO_PATHCONV=1 quiet cl "${msvc_args[@]}"
    "$out/order_cpp.exe"
elif $windows; then
    vswhere="/c/Program Files (x86)/Microsoft Visual Studio/Installer/vswhere.exe"
    vs=""
    if [ -x "$vswhere" ]; then
        vs="$("$vswhere" -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 \
              -property installationPath | tr -d '\r')"
    fi
    if [ -n "$vs" ]; then
        step "C++, MSVC"
        bat="$out/build_msvc.bat"
        printf '%s\r\n' '@echo off' \
            "call \"$vs\\VC\\Auxiliary\\Build\\vcvars64.bat\" >nul 2>nul" \
            "cl ${msvc_args[*]} >nul" \
            'exit /b %errorlevel%' > "$bat"
        MSYS_NO_PATHCONV=1 quiet cmd.exe /c "$(cygpath -w "$bat")"
        "$out/order_cpp.exe"
    else
        skip "C++, MSVC" "no Visual Studio with the C++ tools found"
    fi
else
    skip "C++, MSVC" "Windows only"
fi

# 5. Rust
if have rustc; then
    step "Rust"
    quiet rustc -O --edition 2021 order.rs -o "$out/order_rs$exe"
    "$out/order_rs$exe"
else
    skip "Rust" "rustc not found"
fi
