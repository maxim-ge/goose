// order.goose without the order: the baseline for count_malloc.c, so that the
// heap calls this program makes are the runtime's own.

import std;

struct Item  { sku: u8[varint], qty: varint, cents: varint }
struct Order { id: varint, customer: u8[varint], items: Item[varint] }

fn main() {
    var book: Order[>..] = [];
    for o in book {
        var t = 0;
        for it in o.items { t += it.qty * it.cents; }
        print("- the order: ", o.customer, " owes ", t, " cents over ", o.items.len, " items");
    }
    let bytes = bytes_of(book);
    print("- `bytes_of(book)`: ", bytes.len, " bytes");
    var hex: u8[>..] = [];
    for b in bytes {
        if hex.len > 0 { hex.push(' '); }
        format_uint(hex, b as u64, 16, 2, '0');
    }
    if bytes.len > 0 { print("- bytes: `", hex, "`"); }
}
