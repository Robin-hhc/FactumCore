/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09080(unsigned int count)
{
    const unsigned int limit = 237u;
    return count > limit ? limit : count;
}
