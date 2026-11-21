/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03665(unsigned int count)
{
    const unsigned int limit = 63u;
    return count > limit ? limit : count;
}
