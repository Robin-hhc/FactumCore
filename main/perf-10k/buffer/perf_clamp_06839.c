/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06839(unsigned int count)
{
    const unsigned int limit = 237u;
    return count > limit ? limit : count;
}
