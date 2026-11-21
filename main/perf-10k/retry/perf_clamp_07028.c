/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07028(unsigned int count)
{
    const unsigned int limit = 213u;
    return count > limit ? limit : count;
}
