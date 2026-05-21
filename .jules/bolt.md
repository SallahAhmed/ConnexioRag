## 2024-05-21 - tiktoken get_encoding caching optimization
**Learning:** Initializing dependencies like `tiktoken.get_encoding()` repeatedly inside core processing loops can introduce overhead, even if internal caching mechanisms (like LRU) exist.
**Action:** Moving the initialization of expensive dependencies to the class-level (`__init__`) or global scope ensures they are only loaded once, which follows best practices for performance and clean code design.
