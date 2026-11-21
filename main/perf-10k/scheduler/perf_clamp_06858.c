/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06858(unsigned int count)
{
    const unsigned int limit = 62u;
    return count > limit ? limit : count;
}
