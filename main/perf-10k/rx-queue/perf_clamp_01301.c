/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01301(unsigned int count)
{
    const unsigned int limit = 213u;
    return count > limit ? limit : count;
}
