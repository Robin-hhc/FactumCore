/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07300(unsigned int count)
{
    const unsigned int limit = 106u;
    return count > limit ? limit : count;
}
