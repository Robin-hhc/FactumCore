/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08300(unsigned int count)
{
    const unsigned int limit = 174u;
    return count > limit ? limit : count;
}
