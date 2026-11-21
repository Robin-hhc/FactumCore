/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07587(unsigned int count)
{
    const unsigned int limit = 254u;
    return count > limit ? limit : count;
}
