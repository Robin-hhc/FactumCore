/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07823(unsigned int count)
{
    const unsigned int limit = 33u;
    return count > limit ? limit : count;
}
