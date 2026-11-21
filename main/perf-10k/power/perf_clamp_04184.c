/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04184(unsigned int count)
{
    const unsigned int limit = 171u;
    return count > limit ? limit : count;
}
