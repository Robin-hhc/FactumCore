/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01854(unsigned int count)
{
    const unsigned int limit = 152u;
    return count > limit ? limit : count;
}
