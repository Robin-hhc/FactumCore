/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06857(unsigned int count)
{
    const unsigned int limit = 45u;
    return count > limit ? limit : count;
}
