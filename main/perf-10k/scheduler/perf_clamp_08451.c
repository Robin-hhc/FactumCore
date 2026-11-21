/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08451(unsigned int count)
{
    const unsigned int limit = 251u;
    return count > limit ? limit : count;
}
