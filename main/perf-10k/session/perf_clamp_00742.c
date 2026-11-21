/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00742(unsigned int count)
{
    const unsigned int limit = 172u;
    return count > limit ? limit : count;
}
