/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06100(unsigned int count)
{
    const unsigned int limit = 124u;
    return count > limit ? limit : count;
}
