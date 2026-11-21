/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00390(unsigned int count)
{
    const unsigned int limit = 164u;
    return count > limit ? limit : count;
}
