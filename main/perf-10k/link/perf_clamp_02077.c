/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02077(unsigned int count)
{
    const unsigned int limit = 208u;
    return count > limit ? limit : count;
}
