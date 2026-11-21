/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06166(unsigned int count)
{
    const unsigned int limit = 250u;
    return count > limit ? limit : count;
}
