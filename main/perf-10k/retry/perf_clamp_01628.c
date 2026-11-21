/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01628(unsigned int count)
{
    const unsigned int limit = 45u;
    return count > limit ? limit : count;
}
