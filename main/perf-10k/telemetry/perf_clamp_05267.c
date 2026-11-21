/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05267(unsigned int count)
{
    const unsigned int limit = 156u;
    return count > limit ? limit : count;
}
