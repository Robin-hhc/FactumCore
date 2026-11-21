/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00441(unsigned int count)
{
    const unsigned int limit = 35u;
    return count > limit ? limit : count;
}
