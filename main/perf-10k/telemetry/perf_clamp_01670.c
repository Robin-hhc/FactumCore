/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01670(unsigned int count)
{
    const unsigned int limit = 12u;
    return count > limit ? limit : count;
}
