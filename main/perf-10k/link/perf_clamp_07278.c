/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07278(unsigned int count)
{
    const unsigned int limit = 230u;
    return count > limit ? limit : count;
}
