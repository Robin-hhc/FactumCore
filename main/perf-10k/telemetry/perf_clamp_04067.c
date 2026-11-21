/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04067(unsigned int count)
{
    const unsigned int limit = 174u;
    return count > limit ? limit : count;
}
