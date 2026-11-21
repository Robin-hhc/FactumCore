/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02876(unsigned int count)
{
    const unsigned int limit = 96u;
    return count > limit ? limit : count;
}
