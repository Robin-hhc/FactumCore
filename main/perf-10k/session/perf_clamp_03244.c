/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03244(unsigned int count)
{
    const unsigned int limit = 127u;
    return count > limit ? limit : count;
}
