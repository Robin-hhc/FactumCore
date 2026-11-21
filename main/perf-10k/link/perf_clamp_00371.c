/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00371(unsigned int count)
{
    const unsigned int limit = 90u;
    return count > limit ? limit : count;
}
