/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03037(unsigned int count)
{
    const unsigned int limit = 94u;
    return count > limit ? limit : count;
}
