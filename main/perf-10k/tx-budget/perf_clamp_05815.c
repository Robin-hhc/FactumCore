/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05815(unsigned int count)
{
    const unsigned int limit = 10u;
    return count > limit ? limit : count;
}
