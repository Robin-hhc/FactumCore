/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03051(unsigned int count)
{
    const unsigned int limit = 83u;
    return count > limit ? limit : count;
}
