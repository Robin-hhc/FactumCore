/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03780(unsigned int count)
{
    const unsigned int limit = 26u;
    return count > limit ? limit : count;
}
