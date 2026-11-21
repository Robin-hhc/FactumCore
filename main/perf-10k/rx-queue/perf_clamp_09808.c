/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09808(unsigned int count)
{
    const unsigned int limit = 163u;
    return count > limit ? limit : count;
}
