/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05843(unsigned int count)
{
    const unsigned int limit = 237u;
    return count > limit ? limit : count;
}
