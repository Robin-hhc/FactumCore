/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03589(unsigned int count)
{
    const unsigned int limit = 16u;
    return count > limit ? limit : count;
}
