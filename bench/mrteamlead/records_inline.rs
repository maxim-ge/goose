// MrTeamlead, steps 1-3 as shown in the video (https://www.youtube.com/watch?v=6n-yl2Qolvg):
// 1. no reallocations: the log is created with its final capacity;
// 2. `String` replaced by an inline 15-byte array;
// 3. `match` moved into an `#[inline(always)]` function, `Event` is `Copy`,
//    the pass unrolled by 4.
mod bench;
use bench::*;

const N: i64 = 2_000_000;                // BENCH_N
const PASSES: i64 = 4;

#[derive(Clone, Copy)]
enum Event {
    Tick,
    Move { id: i32, dx: i16, dy: i16 },
    Say { id: i32, text: MyString },
    Quit { id: i32, code: u8 },
}

#[derive(Clone, Copy)]
struct MyString {
    bytes: [u8; 15],
    len: u8,
}

// A word of 4..15 letters from its own chain, so the caller's stream advances
// once per event whatever the variant is.
fn word(seed: u64) -> MyString {
    let mut r = xs_next(seed);
    let n = 4 + xs_mod(r, 12);
    let mut w = MyString { bytes: [0; 15], len: n as u8 };
    for byte in &mut w.bytes[..n as usize] {
        r = xs_next(r);
        *byte = b'a' + xs_mod(r, 26) as u8;
    }
    w
}

#[inline(always)]
fn score(e: Event) -> i64 {
    match e {
        Event::Tick => 1,
        Event::Move { id, dx, dy } => id as i64 + dx as i64 + dy as i64,
        Event::Say { id, text } => id as i64 + text.len as i64 + text.bytes[0] as i64,
        Event::Quit { id, code } => id as i64 + code as i64,
    }
}

fn main() {
    let mut log: Vec<Event> = Vec::with_capacity(N as usize);
    let mut r: u64 = 12345;
    for _ in 0..N {
        r = xs_next(r);
        let k = xs_mod(r, 8);
        let id = xs_mod(r >> 3, 100000) as i32;
        if k < 4 {
            log.push(Event::Move { id, dx: (xs_mod(r >> 20, 201) - 100) as i16,
                                       dy: (xs_mod(r >> 40, 201) - 100) as i16 });
        } else if k < 6 {
            log.push(Event::Say { id, text: word(r) });
        } else if k < 7 {
            log.push(Event::Quit { id, code: xs_mod(r >> 20, 256) as u8 });
        } else {
            log.push(Event::Tick);
        }
    }
    let mut total: i64 = 0;
    for _ in 0..PASSES {
        let mut chunks = log.chunks_exact(4);
        for chunk in &mut chunks {
            total += score(chunk[0]);
            total += score(chunk[1]);
            total += score(chunk[2]);
            total += score(chunk[3]);
        }
        for e in chunks.remainder() {
            total += score(*e);
        }
    }
    emit(log.len() as i64);
    emit(total);
}
