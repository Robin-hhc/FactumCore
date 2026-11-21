/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07798(unsigned int count)
{
    const unsigned int limit = 106u;
    return count > limit ? limit : count;
}
