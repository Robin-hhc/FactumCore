/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03552(unsigned int count)
{
    const unsigned int limit = 134u;
    return count > limit ? limit : count;
}
