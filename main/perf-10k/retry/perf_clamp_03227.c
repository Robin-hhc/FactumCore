/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03227(unsigned int count)
{
    const unsigned int limit = 87u;
    return count > limit ? limit : count;
}
