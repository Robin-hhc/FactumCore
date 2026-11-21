/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06438(unsigned int count)
{
    const unsigned int limit = 143u;
    return count > limit ? limit : count;
}
