/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06237(unsigned int count)
{
    const unsigned int limit = 212u;
    return count > limit ? limit : count;
}
