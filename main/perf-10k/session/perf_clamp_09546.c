/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09546(unsigned int count)
{
    const unsigned int limit = 191u;
    return count > limit ? limit : count;
}
