/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06618(unsigned int count)
{
    const unsigned int limit = 215u;
    return count > limit ? limit : count;
}
