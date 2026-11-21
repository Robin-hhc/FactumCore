/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02517(unsigned int count)
{
    const unsigned int limit = 218u;
    return count > limit ? limit : count;
}
