/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08315(unsigned int count)
{
    const unsigned int limit = 180u;
    return count > limit ? limit : count;
}
