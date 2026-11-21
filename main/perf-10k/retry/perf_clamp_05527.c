/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05527(unsigned int count)
{
    const unsigned int limit = 94u;
    return count > limit ? limit : count;
}
