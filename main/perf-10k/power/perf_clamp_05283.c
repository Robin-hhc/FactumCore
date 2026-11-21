/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05283(unsigned int count)
{
    const unsigned int limit = 179u;
    return count > limit ? limit : count;
}
