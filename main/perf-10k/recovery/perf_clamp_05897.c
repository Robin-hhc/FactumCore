/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05897(unsigned int count)
{
    const unsigned int limit = 159u;
    return count > limit ? limit : count;
}
