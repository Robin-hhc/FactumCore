/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03305(unsigned int count)
{
    const unsigned int limit = 168u;
    return count > limit ? limit : count;
}
