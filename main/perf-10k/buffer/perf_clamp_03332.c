/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03332(unsigned int count)
{
    const unsigned int limit = 129u;
    return count > limit ? limit : count;
}
