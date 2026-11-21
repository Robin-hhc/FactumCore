/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00825(unsigned int count)
{
    const unsigned int limit = 89u;
    return count > limit ? limit : count;
}
