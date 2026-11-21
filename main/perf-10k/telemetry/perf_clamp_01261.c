/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01261(unsigned int count)
{
    const unsigned int limit = 31u;
    return count > limit ? limit : count;
}
