/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05412(unsigned int count)
{
    const unsigned int limit = 131u;
    return count > limit ? limit : count;
}
