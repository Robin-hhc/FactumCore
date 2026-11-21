/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07550(unsigned int count)
{
    const unsigned int limit = 123u;
    return count > limit ? limit : count;
}
