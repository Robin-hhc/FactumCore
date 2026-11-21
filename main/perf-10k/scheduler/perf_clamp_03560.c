/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03560(unsigned int count)
{
    const unsigned int limit = 21u;
    return count > limit ? limit : count;
}
