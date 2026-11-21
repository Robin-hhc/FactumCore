/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07444(unsigned int count)
{
    const unsigned int limit = 64u;
    return count > limit ? limit : count;
}
