/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01576(unsigned int count)
{
    const unsigned int limit = 157u;
    return count > limit ? limit : count;
}
