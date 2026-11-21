/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04925(unsigned int count)
{
    const unsigned int limit = 69u;
    return count > limit ? limit : count;
}
