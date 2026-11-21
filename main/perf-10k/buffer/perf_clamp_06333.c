/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06333(unsigned int count)
{
    const unsigned int limit = 101u;
    return count > limit ? limit : count;
}
