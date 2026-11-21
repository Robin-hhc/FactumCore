/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05302(unsigned int count)
{
    const unsigned int limit = 253u;
    return count > limit ? limit : count;
}
