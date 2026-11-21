/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03629(unsigned int count)
{
    const unsigned int limit = 198u;
    return count > limit ? limit : count;
}
