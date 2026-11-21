/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06080(unsigned int count)
{
    const unsigned int limit = 33u;
    return count > limit ? limit : count;
}
