/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03381(unsigned int count)
{
    const unsigned int limit = 215u;
    return count > limit ? limit : count;
}
