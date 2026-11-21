/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00322(unsigned int count)
{
    const unsigned int limit = 253u;
    return count > limit ? limit : count;
}
