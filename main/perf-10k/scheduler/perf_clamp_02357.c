/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02357(unsigned int count)
{
    const unsigned int limit = 237u;
    return count > limit ? limit : count;
}
