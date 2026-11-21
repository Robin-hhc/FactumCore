/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03182(unsigned int count)
{
    const unsigned int limit = 69u;
    return count > limit ? limit : count;
}
