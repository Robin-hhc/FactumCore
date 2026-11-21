/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08290(unsigned int count)
{
    const unsigned int limit = 253u;
    return count > limit ? limit : count;
}
