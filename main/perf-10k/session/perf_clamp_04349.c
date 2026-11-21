/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04349(unsigned int count)
{
    const unsigned int limit = 237u;
    return count > limit ? limit : count;
}
