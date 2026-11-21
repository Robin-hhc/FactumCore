/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01342(unsigned int count)
{
    const unsigned int limit = 163u;
    return count > limit ? limit : count;
}
