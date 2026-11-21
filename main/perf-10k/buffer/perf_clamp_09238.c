/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09238(unsigned int count)
{
    const unsigned int limit = 184u;
    return count > limit ? limit : count;
}
