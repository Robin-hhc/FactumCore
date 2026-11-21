/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09835(unsigned int count)
{
    const unsigned int limit = 124u;
    return count > limit ? limit : count;
}
