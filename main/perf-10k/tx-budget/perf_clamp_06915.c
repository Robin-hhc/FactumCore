/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06915(unsigned int count)
{
    const unsigned int limit = 35u;
    return count > limit ? limit : count;
}
