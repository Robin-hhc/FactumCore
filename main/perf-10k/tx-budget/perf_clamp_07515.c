/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07515(unsigned int count)
{
    const unsigned int limit = 26u;
    return count > limit ? limit : count;
}
