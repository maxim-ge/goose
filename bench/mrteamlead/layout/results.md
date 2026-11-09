# Layout: results

## Goose

- the order: alice owes 4498 cents over 2 items
- `bytes_of(book)`: 29 bytes
- bytes: `d2 0f 05 61 6c 69 63 65 02 07 53 4b 55 2d 34 34 31 04 9e 1f 05 53 4b 55 2d 37 02 e8 07`

## Goose heap calls

- `order.goose`: 4
- `order_empty.goose`: 4
- added by the order: 0

## C++, g++

- Sizes
  - `sizeof(std::string)`: 32
  - `sizeof(std::vector<Item>)`: 24
  - `sizeof(Item)`: 48
  - short-string capacity: 15
- As in the tutorial
  - total: 160 bytes = `sizeof(Order)` 64 + 96 on the heap
  - heap blocks: 1
  - allocation calls while building: 2
  - items capacity: 2
- One more character in a SKU
  - total: 160 bytes = `sizeof(Order)` 64 + 96 on the heap
  - heap blocks: 1
  - allocation calls while building: 2
  - items capacity: 2
- SKUs of 16 characters
  - total: 194 bytes = `sizeof(Order)` 64 + 130 on the heap
  - heap blocks: 3
  - allocation calls while building: 4
  - items capacity: 2

## C++, MSVC

- Sizes
  - `sizeof(std::string)`: 32
  - `sizeof(std::vector<Item>)`: 24
  - `sizeof(Item)`: 48
  - short-string capacity: 15
- As in the tutorial
  - total: 160 bytes = `sizeof(Order)` 64 + 96 on the heap
  - heap blocks: 1
  - allocation calls while building: 2
  - items capacity: 2
- One more character in a SKU
  - total: 160 bytes = `sizeof(Order)` 64 + 96 on the heap
  - heap blocks: 1
  - allocation calls while building: 2
  - items capacity: 2
- SKUs of 16 characters
  - total: 224 bytes = `sizeof(Order)` 64 + 160 on the heap
  - heap blocks: 3
  - allocation calls while building: 4
  - items capacity: 2

## Rust

- Sizes
  - `size_of::<String>()`: 24
  - `size_of::<Vec<Item>>()`: 24
  - `size_of::<Item>()`: 40
- `collect`, as written
  - total: 233 bytes = `size_of::<Order>()` 56 + 177 on the heap
  - heap blocks: 4
  - allocation calls while building: 4
  - items capacity: 4
- Exact capacity, `shrink_to_fit()`
  - total: 153 bytes = `size_of::<Order>()` 56 + 97 on the heap
  - heap blocks: 4
  - allocation calls while building: 5
  - items capacity: 2
