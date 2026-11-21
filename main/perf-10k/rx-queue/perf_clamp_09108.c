/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09108(unsigned int count)
{
    const unsigned int limit = 215u;
    return count > limit ? limit : count;
}
