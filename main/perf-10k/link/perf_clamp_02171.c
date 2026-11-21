/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02171(unsigned int count)
{
    const unsigned int limit = 63u;
    return count > limit ? limit : count;
}
