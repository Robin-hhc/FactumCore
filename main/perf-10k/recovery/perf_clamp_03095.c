/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03095(unsigned int count)
{
    const unsigned int limit = 84u;
    return count > limit ? limit : count;
}
