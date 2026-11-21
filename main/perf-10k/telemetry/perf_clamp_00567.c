/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00567(unsigned int count)
{
    const unsigned int limit = 185u;
    return count > limit ? limit : count;
}
