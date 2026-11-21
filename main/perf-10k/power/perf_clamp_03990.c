/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03990(unsigned int count)
{
    const unsigned int limit = 110u;
    return count > limit ? limit : count;
}
