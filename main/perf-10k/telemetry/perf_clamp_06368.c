/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06368(unsigned int count)
{
    const unsigned int limit = 198u;
    return count > limit ? limit : count;
}
