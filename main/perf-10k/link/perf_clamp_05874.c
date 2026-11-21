/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05874(unsigned int count)
{
    const unsigned int limit = 17u;
    return count > limit ? limit : count;
}
