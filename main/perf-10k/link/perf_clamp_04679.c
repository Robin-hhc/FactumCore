/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04679(unsigned int count)
{
    const unsigned int limit = 120u;
    return count > limit ? limit : count;
}
