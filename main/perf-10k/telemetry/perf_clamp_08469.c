/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08469(unsigned int count)
{
    const unsigned int limit = 59u;
    return count > limit ? limit : count;
}
