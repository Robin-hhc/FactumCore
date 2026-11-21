/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04585(unsigned int count)
{
    const unsigned int limit = 16u;
    return count > limit ? limit : count;
}
