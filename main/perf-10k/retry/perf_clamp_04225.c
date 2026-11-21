/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04225(unsigned int count)
{
    const unsigned int limit = 121u;
    return count > limit ? limit : count;
}
