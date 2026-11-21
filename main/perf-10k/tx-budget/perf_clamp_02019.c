/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02019(unsigned int count)
{
    const unsigned int limit = 218u;
    return count > limit ? limit : count;
}
