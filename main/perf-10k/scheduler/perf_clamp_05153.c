/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05153(unsigned int count)
{
    const unsigned int limit = 210u;
    return count > limit ? limit : count;
}
