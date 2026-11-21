/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05568(unsigned int count)
{
    const unsigned int limit = 44u;
    return count > limit ? limit : count;
}
