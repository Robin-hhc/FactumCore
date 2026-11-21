/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00077(unsigned int count)
{
    const unsigned int limit = 72u;
    return count > limit ? limit : count;
}
