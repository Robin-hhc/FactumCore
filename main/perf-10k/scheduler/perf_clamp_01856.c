/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01856(unsigned int count)
{
    const unsigned int limit = 186u;
    return count > limit ? limit : count;
}
