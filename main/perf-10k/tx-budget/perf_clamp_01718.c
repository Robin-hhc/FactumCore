/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01718(unsigned int count)
{
    const unsigned int limit = 81u;
    return count > limit ? limit : count;
}
