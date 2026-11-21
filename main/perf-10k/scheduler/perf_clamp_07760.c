/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07760(unsigned int count)
{
    const unsigned int limit = 207u;
    return count > limit ? limit : count;
}
