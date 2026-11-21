/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02148(unsigned int count)
{
    const unsigned int limit = 170u;
    return count > limit ? limit : count;
}
