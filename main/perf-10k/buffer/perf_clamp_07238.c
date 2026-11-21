/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07238(unsigned int count)
{
    const unsigned int limit = 48u;
    return count > limit ? limit : count;
}
