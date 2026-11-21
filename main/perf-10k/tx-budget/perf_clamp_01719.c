/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01719(unsigned int count)
{
    const unsigned int limit = 98u;
    return count > limit ? limit : count;
}
