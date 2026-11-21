/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03771(unsigned int count)
{
    const unsigned int limit = 122u;
    return count > limit ? limit : count;
}
