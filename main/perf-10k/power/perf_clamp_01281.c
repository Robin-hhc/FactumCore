/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01281(unsigned int count)
{
    const unsigned int limit = 122u;
    return count > limit ? limit : count;
}
