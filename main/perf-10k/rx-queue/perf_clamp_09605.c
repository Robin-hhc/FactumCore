/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09605(unsigned int count)
{
    const unsigned int limit = 198u;
    return count > limit ? limit : count;
}
