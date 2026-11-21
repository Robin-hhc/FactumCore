/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01849(unsigned int count)
{
    const unsigned int limit = 67u;
    return count > limit ? limit : count;
}
