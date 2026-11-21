/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03763(unsigned int count)
{
    const unsigned int limit = 235u;
    return count > limit ? limit : count;
}
