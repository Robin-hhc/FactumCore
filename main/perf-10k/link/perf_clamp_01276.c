/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01276(unsigned int count)
{
    const unsigned int limit = 37u;
    return count > limit ? limit : count;
}
