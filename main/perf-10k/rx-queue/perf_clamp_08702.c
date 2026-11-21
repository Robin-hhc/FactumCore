/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08702(unsigned int count)
{
    const unsigned int limit = 36u;
    return count > limit ? limit : count;
}
