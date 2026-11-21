/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06432(unsigned int count)
{
    const unsigned int limit = 41u;
    return count > limit ? limit : count;
}
