/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03368(unsigned int count)
{
    const unsigned int limit = 243u;
    return count > limit ? limit : count;
}
