/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06579(unsigned int count)
{
    const unsigned int limit = 50u;
    return count > limit ? limit : count;
}
