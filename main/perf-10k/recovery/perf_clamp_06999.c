/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06999(unsigned int count)
{
    const unsigned int limit = 218u;
    return count > limit ? limit : count;
}
