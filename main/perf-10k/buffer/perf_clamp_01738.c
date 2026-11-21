/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01738(unsigned int count)
{
    const unsigned int limit = 172u;
    return count > limit ? limit : count;
}
