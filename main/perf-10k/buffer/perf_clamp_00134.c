/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00134(unsigned int count)
{
    const unsigned int limit = 45u;
    return count > limit ? limit : count;
}
