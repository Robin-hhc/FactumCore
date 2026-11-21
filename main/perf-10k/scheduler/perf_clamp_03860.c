/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03860(unsigned int count)
{
    const unsigned int limit = 141u;
    return count > limit ? limit : count;
}
