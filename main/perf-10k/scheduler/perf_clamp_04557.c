/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04557(unsigned int count)
{
    const unsigned int limit = 38u;
    return count > limit ? limit : count;
}
