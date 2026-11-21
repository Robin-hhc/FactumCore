/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06716(unsigned int count)
{
    const unsigned int limit = 138u;
    return count > limit ? limit : count;
}
