/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01006(unsigned int count)
{
    const unsigned int limit = 178u;
    return count > limit ? limit : count;
}
