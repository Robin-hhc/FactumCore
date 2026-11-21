/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02957(unsigned int count)
{
    const unsigned int limit = 228u;
    return count > limit ? limit : count;
}
