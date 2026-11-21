/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01194(unsigned int count)
{
    const unsigned int limit = 137u;
    return count > limit ? limit : count;
}
