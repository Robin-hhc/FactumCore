/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09298(unsigned int count)
{
    const unsigned int limit = 208u;
    return count > limit ? limit : count;
}
