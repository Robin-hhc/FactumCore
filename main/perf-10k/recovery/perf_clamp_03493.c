/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03493(unsigned int count)
{
    const unsigned int limit = 127u;
    return count > limit ? limit : count;
}
