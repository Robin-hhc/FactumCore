/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06050(unsigned int count)
{
    const unsigned int limit = 21u;
    return count > limit ? limit : count;
}
