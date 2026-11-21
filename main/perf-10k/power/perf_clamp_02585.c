/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02585(unsigned int count)
{
    const unsigned int limit = 129u;
    return count > limit ? limit : count;
}
