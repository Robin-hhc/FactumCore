/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07747(unsigned int count)
{
    const unsigned int limit = 235u;
    return count > limit ? limit : count;
}
