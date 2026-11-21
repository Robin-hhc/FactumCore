/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04813(unsigned int count)
{
    const unsigned int limit = 157u;
    return count > limit ? limit : count;
}
