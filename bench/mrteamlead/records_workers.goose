// records.goose with the passes spread over worker threads, the counterpart
// of records_rayon.rs for Goose's variable-mode log. Goose threads share no
// memory, so the log is sent to the workers in chunks through a typed queue,
// one copy per chunk.
//
// Kept from records.goose: the variable-mode enum (each event takes its own
// size, the text inline behind a varint length), the sequential generation
// and the score.
// Changed: main starts one worker per hardware thread and sends the log in
// chunks; a worker runs all passes over a chunk and sends back its sum. A
// log of variable-size events cannot be indexed or sliced, so main walks it
// and copies each chunk's events into a buffer before sending it. At most two
// chunks per worker are in flight, so the copies take little memory beyond
// the log itself.
//
// Usage: records_workers [chunk], where chunk is the number of events per
// message, 4096 by default.

import rng;
import std;
import os;

let N = 2000000;                         // BENCH_N
let PASSES = 4;
let CHUNK = 4096;                        // events per message, unless given as the first argument

enum Event {
    Tick,
    Move { id: i32, dx: i16, dy: i16 },
    Say  { id: i32, text: u8[varint] },
    Quit { id: i32, code: u8 },
}

struct Chunk   { events: Event..[] }     // flat: crosses the queue as one copy
struct Partial { sum: i64 }

// A word of 4..15 letters from its own chain, so the caller's stream advances
// once per event whatever the variant is.
fn word(seed: u64) -> u8[varint] {
    var w: u8[>..] = [];
    var r = xs_next(seed);
    let n = 4 + xs_mod(r, 12);
    for i in n {
        r = xs_next(r);
        w.push(('a' + xs_mod(r, 26)) as! u8);
    }
    return w;
}

// Takes chunks until an empty one; for each, runs all passes and sends back
// the sum.
thread_fn worker() {
    loop {
        let c = qget<Chunk>();
        guard c.events.len > 0 else { break; }
        var total = 0;
        for p in PASSES {
            for e in c.events {
                total += (match e {
                    Tick    => 1,
                    Move m  => m.id + m.dx + m.dy,
                    Say &s  => s.id + s.text.len + s.text[0],
                    Quit q  => q.id + q.code,
                });
            }
        }
        qput(Partial { sum: total });
    }
}

fn chunk_size() -> i64 {
    guard arg_count() > 1 else { return CHUNK; }
    var s: u8[>..] = [];
    arg(1, s);
    let n, ok = parse_int(s);
    guard ok && n > 0 else { abort("records_workers: the chunk size must be a positive integer"); }
    return n;
}

fn main() {
    let chunk = chunk_size();
    var log: Event..[>..] = [];
    var r: u64 = 12345;
    for i in N {
        r = xs_next(r);
        let k = xs_mod(r, 8);
        let id = xs_mod(r >> 3, 100000);
        if k < 4 {
            log.push(Event.Move { id: id as i32,
                                  dx: (xs_mod(r >> 20, 201) - 100) as i16,
                                  dy: (xs_mod(r >> 40, 201) - 100) as i16 });
        } else if k < 6 {
            log.push(Event.Say { id: id as i32, text: word(r) });
        } else if k < 7 {
            log.push(Event.Quit { id: id as i32, code: xs_mod(r >> 20, 256) as u8 });
        } else {
            log.push(Event.Tick);
        }
    }
    let n = max(1, hardware_threads());
    var ids: i64[>..] = [];
    for t in n { ids.push(thread_spawn(worker)); }
    // qput never waits, so main bounds the chunks in flight itself: past
    // 2n, each new chunk first takes one result.
    let inflight = 2 * n;
    var sent = 0;
    var walked = 0;
    var total = 0;
    var buf: Event..[>..] = [];
    for e in log {
        buf.push(copy(e));
        walked++;
        if buf.len == chunk || walked == log.len {
            if sent >= inflight { total += qget<Partial>().sum; }
            qput(Chunk { events: copy(buf) });
            sent++;
            buf.clear();
        }
    }
    for i in min(sent, inflight) { total += qget<Partial>().sum; }
    for t in n { qput(Chunk { events: [] }); }   // an empty chunk stops a worker
    for id in ids { thread_wait(id); }
    print(log.len);
    print(total);
}
