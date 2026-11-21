/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07193(unsigned int count)
{
    const unsigned int limit = 30u;
    return count > limit ? limit : count;
}
