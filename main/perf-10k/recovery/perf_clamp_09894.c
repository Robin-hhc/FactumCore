/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09894(unsigned int count)
{
    const unsigned int limit = 131u;
    return count > limit ? limit : count;
}
