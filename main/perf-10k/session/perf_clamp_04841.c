/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04841(unsigned int count)
{
    const unsigned int limit = 135u;
    return count > limit ? limit : count;
}
