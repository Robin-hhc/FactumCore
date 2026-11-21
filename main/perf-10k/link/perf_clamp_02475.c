/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02475(unsigned int count)
{
    const unsigned int limit = 251u;
    return count > limit ? limit : count;
}
