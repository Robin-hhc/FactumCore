/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03500(unsigned int count)
{
    const unsigned int limit = 246u;
    return count > limit ? limit : count;
}
