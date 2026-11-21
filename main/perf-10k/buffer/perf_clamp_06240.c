/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06240(unsigned int count)
{
    const unsigned int limit = 14u;
    return count > limit ? limit : count;
}
