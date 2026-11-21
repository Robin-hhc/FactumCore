/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09679(unsigned int count)
{
    const unsigned int limit = 211u;
    return count > limit ? limit : count;
}
