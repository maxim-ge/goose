/* Counts the heap calls of the code it is linked with, through
   gcc -Wl,--wrap=malloc,--wrap=calloc,--wrap=realloc: every call to these
   in the program's own object files goes through the wrappers below. */
#include <stdio.h>
#include <stdlib.h>

void *__real_malloc(size_t n);
void *__real_calloc(size_t n, size_t s);
void *__real_realloc(void *p, size_t n);

static long calls;

void *__wrap_malloc(size_t n) { calls++; return __real_malloc(n); }
void *__wrap_calloc(size_t n, size_t s) { calls++; return __real_calloc(n, s); }
void *__wrap_realloc(void *p, size_t n) { calls++; return __real_realloc(p, n); }

__attribute__((destructor)) static void report(void) {
    fprintf(stderr, "heap calls: %ld\n", calls);      /* malloc, calloc and realloc */
}
