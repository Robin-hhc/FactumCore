/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07276(unsigned int count)
{
    const unsigned int limit = 196u;
    return count > limit ? limit : count;
}
