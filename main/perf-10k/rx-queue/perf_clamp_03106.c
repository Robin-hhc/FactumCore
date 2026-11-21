/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03106(unsigned int count)
{
    const unsigned int limit = 22u;
    return count > limit ? limit : count;
}
