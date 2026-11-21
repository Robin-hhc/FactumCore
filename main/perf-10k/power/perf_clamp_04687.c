/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04687(unsigned int count)
{
    const unsigned int limit = 256u;
    return count > limit ? limit : count;
}
