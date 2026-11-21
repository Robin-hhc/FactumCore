/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02976(unsigned int count)
{
    const unsigned int limit = 53u;
    return count > limit ? limit : count;
}
