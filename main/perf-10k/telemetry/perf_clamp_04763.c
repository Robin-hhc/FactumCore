/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04763(unsigned int count)
{
    const unsigned int limit = 54u;
    return count > limit ? limit : count;
}
