/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09173(unsigned int count)
{
    const unsigned int limit = 75u;
    return count > limit ? limit : count;
}
