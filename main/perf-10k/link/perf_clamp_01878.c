/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01878(unsigned int count)
{
    const unsigned int limit = 62u;
    return count > limit ? limit : count;
}
