/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03344(unsigned int count)
{
    const unsigned int limit = 84u;
    return count > limit ? limit : count;
}
