/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03743(unsigned int count)
{
    const unsigned int limit = 144u;
    return count > limit ? limit : count;
}
