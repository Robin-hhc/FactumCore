/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09273(unsigned int count)
{
    const unsigned int limit = 32u;
    return count > limit ? limit : count;
}
