/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02815(unsigned int count)
{
    const unsigned int limit = 55u;
    return count > limit ? limit : count;
}
