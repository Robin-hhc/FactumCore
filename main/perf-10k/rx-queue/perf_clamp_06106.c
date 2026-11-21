/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06106(unsigned int count)
{
    const unsigned int limit = 226u;
    return count > limit ? limit : count;
}
