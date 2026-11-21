/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09486(unsigned int count)
{
    const unsigned int limit = 167u;
    return count > limit ? limit : count;
}
