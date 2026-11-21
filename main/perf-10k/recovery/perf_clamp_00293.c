/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00293(unsigned int count)
{
    const unsigned int limit = 9u;
    return count > limit ? limit : count;
}
