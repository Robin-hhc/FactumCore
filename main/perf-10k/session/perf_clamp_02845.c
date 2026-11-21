/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02845(unsigned int count)
{
    const unsigned int limit = 67u;
    return count > limit ? limit : count;
}
