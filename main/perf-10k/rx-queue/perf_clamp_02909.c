/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02909(unsigned int count)
{
    const unsigned int limit = 159u;
    return count > limit ? limit : count;
}
