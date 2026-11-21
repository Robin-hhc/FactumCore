/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03768(unsigned int count)
{
    const unsigned int limit = 71u;
    return count > limit ? limit : count;
}
