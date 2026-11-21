/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00115(unsigned int count)
{
    const unsigned int limit = 220u;
    return count > limit ? limit : count;
}
