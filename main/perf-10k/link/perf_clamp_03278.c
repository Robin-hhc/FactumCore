/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03278(unsigned int count)
{
    const unsigned int limit = 207u;
    return count > limit ? limit : count;
}
