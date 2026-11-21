/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09743(unsigned int count)
{
    const unsigned int limit = 54u;
    return count > limit ? limit : count;
}
