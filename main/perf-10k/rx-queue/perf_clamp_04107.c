/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04107(unsigned int count)
{
    const unsigned int limit = 107u;
    return count > limit ? limit : count;
}
