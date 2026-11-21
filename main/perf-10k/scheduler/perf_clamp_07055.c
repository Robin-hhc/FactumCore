/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07055(unsigned int count)
{
    const unsigned int limit = 174u;
    return count > limit ? limit : count;
}
