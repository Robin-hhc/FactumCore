/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06037(unsigned int count)
{
    const unsigned int limit = 49u;
    return count > limit ? limit : count;
}
