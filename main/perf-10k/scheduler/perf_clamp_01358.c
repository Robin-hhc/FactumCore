/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01358(unsigned int count)
{
    const unsigned int limit = 186u;
    return count > limit ? limit : count;
}
