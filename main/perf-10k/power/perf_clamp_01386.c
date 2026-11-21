/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01386(unsigned int count)
{
    const unsigned int limit = 164u;
    return count > limit ? limit : count;
}
