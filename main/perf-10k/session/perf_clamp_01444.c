/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01444(unsigned int count)
{
    const unsigned int limit = 154u;
    return count > limit ? limit : count;
}
