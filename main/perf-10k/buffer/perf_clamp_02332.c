/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02332(unsigned int count)
{
    const unsigned int limit = 61u;
    return count > limit ? limit : count;
}
