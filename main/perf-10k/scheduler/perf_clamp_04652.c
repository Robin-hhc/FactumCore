/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04652(unsigned int count)
{
    const unsigned int limit = 159u;
    return count > limit ? limit : count;
}
