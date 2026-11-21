/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00601(unsigned int count)
{
    const unsigned int limit = 16u;
    return count > limit ? limit : count;
}
