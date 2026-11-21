/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03197(unsigned int count)
{
    const unsigned int limit = 75u;
    return count > limit ? limit : count;
}
