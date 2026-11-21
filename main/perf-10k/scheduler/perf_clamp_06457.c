/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06457(unsigned int count)
{
    const unsigned int limit = 217u;
    return count > limit ? limit : count;
}
