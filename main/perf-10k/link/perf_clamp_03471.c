/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03471(unsigned int count)
{
    const unsigned int limit = 251u;
    return count > limit ? limit : count;
}
