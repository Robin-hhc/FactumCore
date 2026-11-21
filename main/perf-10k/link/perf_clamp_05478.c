/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05478(unsigned int count)
{
    const unsigned int limit = 8u;
    return count > limit ? limit : count;
}
