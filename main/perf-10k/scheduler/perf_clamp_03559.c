/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03559(unsigned int count)
{
    const unsigned int limit = 253u;
    return count > limit ? limit : count;
}
