/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03569(unsigned int count)
{
    const unsigned int limit = 174u;
    return count > limit ? limit : count;
}
