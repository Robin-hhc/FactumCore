/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01806(unsigned int count)
{
    const unsigned int limit = 83u;
    return count > limit ? limit : count;
}
