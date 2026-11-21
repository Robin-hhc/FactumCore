/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01792(unsigned int count)
{
    const unsigned int limit = 94u;
    return count > limit ? limit : count;
}
