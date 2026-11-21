/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06358(unsigned int count)
{
    const unsigned int limit = 28u;
    return count > limit ? limit : count;
}
