/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03739(unsigned int count)
{
    const unsigned int limit = 76u;
    return count > limit ? limit : count;
}
