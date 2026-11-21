/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04794(unsigned int count)
{
    const unsigned int limit = 83u;
    return count > limit ? limit : count;
}
