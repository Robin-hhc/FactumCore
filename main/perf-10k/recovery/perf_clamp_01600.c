/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01600(unsigned int count)
{
    const unsigned int limit = 67u;
    return count > limit ? limit : count;
}
