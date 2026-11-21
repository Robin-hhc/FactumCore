/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01311(unsigned int count)
{
    const unsigned int limit = 134u;
    return count > limit ? limit : count;
}
