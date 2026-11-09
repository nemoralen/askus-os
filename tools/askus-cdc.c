/* ASKus OS: content-defined chunking for fast (delta) updates.
 * Prints "offset length" for each chunk of a file. Chunk borders depend only on the
 * bytes around them, so a change in one place of the image only changes the chunks
 * there - the rest stay identical and the updater re-uses them from the USB stick.
 * Build: gcc -O2 -o askus-cdc askus-cdc.c */
#include <stdio.h>
#include <stdint.h>

#define MIN_SIZE (64u * 1024u)          /* no chunk smaller than 64 KiB   */
#define MAX_SIZE (4u * 1024u * 1024u)   /* no chunk larger than 4 MiB     */
#define CUT_MASK 0xFFFFC00000000000ULL  /* 18 bits -> ~256 KiB on average */

static uint64_t gear[256];

static uint64_t splitmix(uint64_t *x) {
    uint64_t z = (*x += 0x9E3779B97F4A7C15ULL);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return z ^ (z >> 31);
}

int main(int argc, char **argv) {
    if (argc != 2) { fprintf(stderr, "usage: askus-cdc FILE\n"); return 2; }
    FILE *f = fopen(argv[1], "rb");
    if (!f) { perror(argv[1]); return 1; }
    uint64_t seed = 0x41534B7573ULL;    /* fixed: every build must cut the same way */
    for (int i = 0; i < 256; i++) gear[i] = splitmix(&seed);
    static unsigned char buf[1 << 20];
    size_t n;
    uint64_t off = 0, start = 0, h = 0;
    while ((n = fread(buf, 1, sizeof buf, f)) > 0) {
        for (size_t i = 0; i < n; i++) {
            h = (h << 1) + gear[buf[i]];
            off++;
            uint64_t len = off - start;
            if ((len >= MIN_SIZE && (h & CUT_MASK) == 0) || len >= MAX_SIZE) {
                printf("%llu %llu\n", (unsigned long long)start, (unsigned long long)len);
                start = off;
                h = 0;
            }
        }
    }
    if (ferror(f)) { perror("read"); return 1; }
    if (off > start) printf("%llu %llu\n", (unsigned long long)start, (unsigned long long)(off - start));
    return 0;
}
