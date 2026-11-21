/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06649(unsigned int count)
{
    const unsigned int limit = 244u;
    return count > limit ? limit : count;
}
