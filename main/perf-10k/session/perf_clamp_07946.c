/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07946(unsigned int count)
{
    const unsigned int limit = 132u;
    return count > limit ? limit : count;
}
