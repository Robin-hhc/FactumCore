/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04595(unsigned int count)
{
    const unsigned int limit = 186u;
    return count > limit ? limit : count;
}
