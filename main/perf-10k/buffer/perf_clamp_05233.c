/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05233(unsigned int count)
{
    const unsigned int limit = 76u;
    return count > limit ? limit : count;
}
