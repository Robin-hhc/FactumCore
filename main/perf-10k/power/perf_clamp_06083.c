/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06083(unsigned int count)
{
    const unsigned int limit = 84u;
    return count > limit ? limit : count;
}
