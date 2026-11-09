// Tutorial section 8, "Nested data stays inline": the same order as
// String + Vec<Item>. Counts what the tutorial counts: size_of::<Order>() plus
// the heap blocks the order owns, at their requested sizes (no allocator
// header or rounding), through a counting global allocator.
use std::alloc::{GlobalAlloc, Layout, System};
use std::mem::size_of;
use std::sync::atomic::{AtomicIsize, Ordering::Relaxed};

struct Counting;
static CALLS: AtomicIsize = AtomicIsize::new(0);
static LIVE: AtomicIsize = AtomicIsize::new(0);
static LIVE_BYTES: AtomicIsize = AtomicIsize::new(0);

unsafe impl GlobalAlloc for Counting {
    unsafe fn alloc(&self, l: Layout) -> *mut u8 {
        CALLS.fetch_add(1, Relaxed);
        LIVE.fetch_add(1, Relaxed);
        LIVE_BYTES.fetch_add(l.size() as isize, Relaxed);
        unsafe { System.alloc(l) }
    }
    unsafe fn dealloc(&self, p: *mut u8, l: Layout) {
        LIVE.fetch_sub(1, Relaxed);
        LIVE_BYTES.fetch_sub(l.size() as isize, Relaxed);
        unsafe { System.dealloc(p, l) }
    }
    unsafe fn realloc(&self, p: *mut u8, l: Layout, new: usize) -> *mut u8 {
        CALLS.fetch_add(1, Relaxed);
        LIVE_BYTES.fetch_add(new as isize - l.size() as isize, Relaxed);
        unsafe { System.realloc(p, l, new) }
    }
}

#[global_allocator]
static A: Counting = Counting;

#[allow(dead_code)]
struct Item { sku: String, qty: i64, cents: i64 }
#[allow(dead_code)]
struct Order { id: i64, customer: String, items: Vec<Item> }

// "SKU:qty:cents;..." -> items
fn parse_items(field: &str) -> Vec<Item> {
    field.split(';').map(|p| {
        let mut f = p.split(':');
        let sku = f.next().unwrap().to_string();
        let qty = f.next().unwrap().parse().unwrap();
        let cents = f.next().unwrap().parse().unwrap();
        Item { sku, qty, cents }
    }).collect()
}

// One case as a Markdown item with sub-items.
fn measure(what: &str, exact: bool) {
    let (calls0, live0, bytes0) = (CALLS.load(Relaxed), LIVE.load(Relaxed), LIVE_BYTES.load(Relaxed));
    let mut items = parse_items("SKU-441:2:1999;SKU-7:1:500");
    if exact { items.shrink_to_fit(); }
    let o = Order { id: 1001, customer: "alice".to_string(), items };
    let (live, bytes) = (LIVE.load(Relaxed) - live0, LIVE_BYTES.load(Relaxed) - bytes0);
    println!("- {what}");
    println!("  - total: {} bytes = `size_of::<Order>()` {} + {bytes} on the heap",
             size_of::<Order>() as isize + bytes, size_of::<Order>());
    println!("  - heap blocks: {live}");
    println!("  - allocation calls while building: {}", CALLS.load(Relaxed) - calls0);
    println!("  - items capacity: {}", o.items.capacity());
}

fn main() {
    println!("- Sizes");
    println!("  - `size_of::<String>()`: {}", size_of::<String>());
    println!("  - `size_of::<Vec<Item>>()`: {}", size_of::<Vec<Item>>());
    println!("  - `size_of::<Item>()`: {}", size_of::<Item>());
    measure("`collect`, as written", false);
    measure("Exact capacity, `shrink_to_fit()`", true);
}
