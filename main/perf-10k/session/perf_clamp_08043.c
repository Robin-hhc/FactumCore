/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08043(unsigned int count)
{
    const unsigned int limit = 38u;
    return count > limit ? limit : count;
}
