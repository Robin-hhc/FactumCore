/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00095(unsigned int count)
{
    const unsigned int limit = 129u;
    return count > limit ? limit : count;
}
