/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03385(unsigned int count)
{
    const unsigned int limit = 34u;
    return count > limit ? limit : count;
}
