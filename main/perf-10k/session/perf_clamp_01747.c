/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01747(unsigned int count)
{
    const unsigned int limit = 76u;
    return count > limit ? limit : count;
}
