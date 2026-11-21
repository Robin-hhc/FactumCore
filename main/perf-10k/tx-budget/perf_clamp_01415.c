/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01415(unsigned int count)
{
    const unsigned int limit = 159u;
    return count > limit ? limit : count;
}
