/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06569(unsigned int count)
{
    const unsigned int limit = 129u;
    return count > limit ? limit : count;
}
