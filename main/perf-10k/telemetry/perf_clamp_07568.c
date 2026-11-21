/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07568(unsigned int count)
{
    const unsigned int limit = 180u;
    return count > limit ? limit : count;
}
