/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07486(unsigned int count)
{
    const unsigned int limit = 31u;
    return count > limit ? limit : count;
}
