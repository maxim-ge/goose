// Tutorial section 8, "Nested data stays inline": the same order as
// std::string + std::vector<Item>. Counts what the tutorial counts:
// sizeof(Order) plus the heap blocks the order owns, at their requested sizes
// (no allocator header or rounding), through a replaced global operator new.
#include <cstdio>
#include <cstdlib>
#include <new>
#include <string>
#include <string_view>
#include <vector>

static long g_calls = 0, g_live = 0, g_live_bytes = 0;

void *operator new(std::size_t n) {
    g_calls++; g_live++; g_live_bytes += (long)n;
    char *b = (char *)std::malloc(n + 16);
    if (!b) throw std::bad_alloc();
    *(std::size_t *)b = n;
    return b + 16;
}
void operator delete(void *p) noexcept {
    if (!p) return;
    char *b = (char *)p - 16;
    g_live--; g_live_bytes -= (long)*(std::size_t *)b;
    std::free(b);
}
void operator delete(void *p, std::size_t) noexcept { operator delete(p); }

struct Item  { std::string sku; long long qty; long long cents; };
struct Order { long long id; std::string customer; std::vector<Item> items; };

static long long to_int(std::string_view s) { return std::strtoll(std::string(s).c_str(), nullptr, 10); }

// "SKU:qty:cents;..." -> items
static std::vector<Item> parse_items(std::string_view field) {
    std::vector<Item> items;
    while (!field.empty()) {
        size_t end = field.find(';');
        std::string_view part = field.substr(0, end);
        size_t a = part.find(':'), b = part.find(':', a + 1);
        items.push_back(Item { std::string(part.substr(0, a)),
                               to_int(part.substr(a + 1, b - a - 1)), to_int(part.substr(b + 1)) });
        field = end == std::string_view::npos ? std::string_view() : field.substr(end + 1);
    }
    return items;
}

// One case as a Markdown item with sub-items.
static void measure(const char *what, const char *items) {
    long calls0 = g_calls, live0 = g_live, bytes0 = g_live_bytes;
    {
        Order o { 1001, "alice", parse_items(items) };
        long live = g_live - live0, bytes = g_live_bytes - bytes0;
        std::printf("- %s\n", what);
        std::printf("  - total: %zu bytes = `sizeof(Order)` %zu + %ld on the heap\n",
                    sizeof(Order) + (size_t)bytes, sizeof(Order), bytes);
        std::printf("  - heap blocks: %ld\n", live);
        std::printf("  - allocation calls while building: %ld\n", g_calls - calls0);
        std::printf("  - items capacity: %zu\n", o.items.capacity());
    }
}

int main() {
    std::printf("- Sizes\n");
    std::printf("  - `sizeof(std::string)`: %zu\n", sizeof(std::string));
    std::printf("  - `sizeof(std::vector<Item>)`: %zu\n", sizeof(std::vector<Item>));
    std::printf("  - `sizeof(Item)`: %zu\n", sizeof(Item));
    std::printf("  - short-string capacity: %zu\n", std::string().capacity());
    measure("As in the tutorial", "SKU-441:2:1999;SKU-7:1:500");
    measure("One more character in a SKU", "SKU-4410:2:1999;SKU-7:1:500");
    measure("SKUs of 16 characters", "SKU-441-ABCDEFGH:2:1999;SKU-7-ABCDEFGHIJ:1:500");
    return 0;
}
