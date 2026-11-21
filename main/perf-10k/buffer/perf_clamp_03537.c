/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03537(unsigned int count)
{
    const unsigned int limit = 128u;
    return count > limit ? limit : count;
}
