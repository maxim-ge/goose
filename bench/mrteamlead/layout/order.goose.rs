// A copy of order.goose with the .rs extension, only so that GitHub and
// editors highlight its syntax: Goose looks enough like Rust for that. It is
// not Rust and is not compiled; order.goose is the source to build and edit.
//
// Tutorial section 8, "Nested data stays inline": the order from the text,
// and how many bytes it takes. Prints a Markdown list: the tutorial's line,
// the size of the book and its bytes as hex.

import std;

struct Item  { sku: u8[varint], qty: varint, cents: varint }
struct Order { id: varint, customer: u8[varint], items: Item[varint] }

// "SKU:qty:cents;..." -> items, built straight into the field that gets them
fn parse_items(field: u8[:]) -> Item[>..] {
    var items: Item[>..] = [];
    each_split(field, ';') {
        let p = split(it, ':');
        let qty, ok1 = parse_int(p[1]);
        let cents, ok2 = parse_int(p[2]);
        assert(ok1 && ok2);
        items.push(Item { sku: p[0], qty: qty, cents: cents });
    };
    return items;
}

fn main() {
    var book: Order[>..] = [];
    book.push(Order { id: 1001, customer: "alice",
                      items: parse_items("SKU-441:2:1999;SKU-7:1:500") });
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
