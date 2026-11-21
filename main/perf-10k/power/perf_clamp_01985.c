/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01985(unsigned int count)
{
    const unsigned int limit = 138u;
    return count > limit ? limit : count;
}
