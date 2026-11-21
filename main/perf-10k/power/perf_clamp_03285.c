/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03285(unsigned int count)
{
    const unsigned int limit = 77u;
    return count > limit ? limit : count;
}
