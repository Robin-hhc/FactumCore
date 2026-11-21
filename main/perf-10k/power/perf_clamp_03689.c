/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03689(unsigned int count)
{
    const unsigned int limit = 222u;
    return count > limit ? limit : count;
}
