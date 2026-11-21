/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08612(unsigned int count)
{
    const unsigned int limit = 249u;
    return count > limit ? limit : count;
}
