/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04237(unsigned int count)
{
    const unsigned int limit = 76u;
    return count > limit ? limit : count;
}
