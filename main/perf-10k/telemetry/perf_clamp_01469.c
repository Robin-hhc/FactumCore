/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01469(unsigned int count)
{
    const unsigned int limit = 81u;
    return count > limit ? limit : count;
}
