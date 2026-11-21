/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06395(unsigned int count)
{
    const unsigned int limit = 159u;
    return count > limit ? limit : count;
}
