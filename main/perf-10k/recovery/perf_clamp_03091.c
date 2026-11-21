/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03091(unsigned int count)
{
    const unsigned int limit = 16u;
    return count > limit ? limit : count;
}
