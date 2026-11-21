/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08496(unsigned int count)
{
    const unsigned int limit = 20u;
    return count > limit ? limit : count;
}
