/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05032(unsigned int count)
{
    const unsigned int limit = 145u;
    return count > limit ? limit : count;
}
