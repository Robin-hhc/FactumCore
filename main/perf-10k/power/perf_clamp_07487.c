/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07487(unsigned int count)
{
    const unsigned int limit = 48u;
    return count > limit ? limit : count;
}
