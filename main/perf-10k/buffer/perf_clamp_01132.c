/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01132(unsigned int count)
{
    const unsigned int limit = 79u;
    return count > limit ? limit : count;
}
