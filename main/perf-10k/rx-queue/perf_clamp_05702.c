/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05702(unsigned int count)
{
    const unsigned int limit = 81u;
    return count > limit ? limit : count;
}
