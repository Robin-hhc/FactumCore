/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05585(unsigned int count)
{
    const unsigned int limit = 84u;
    return count > limit ? limit : count;
}
