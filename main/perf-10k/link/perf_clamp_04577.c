/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04577(unsigned int count)
{
    const unsigned int limit = 129u;
    return count > limit ? limit : count;
}
