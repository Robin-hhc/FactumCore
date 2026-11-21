/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02304(unsigned int count)
{
    const unsigned int limit = 83u;
    return count > limit ? limit : count;
}
