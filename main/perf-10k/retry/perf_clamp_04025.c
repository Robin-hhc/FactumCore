/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04025(unsigned int count)
{
    const unsigned int limit = 207u;
    return count > limit ? limit : count;
}
