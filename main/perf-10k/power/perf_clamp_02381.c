/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02381(unsigned int count)
{
    const unsigned int limit = 147u;
    return count > limit ? limit : count;
}
