/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04688(unsigned int count)
{
    const unsigned int limit = 24u;
    return count > limit ? limit : count;
}
