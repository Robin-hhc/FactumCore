/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09771(unsigned int count)
{
    const unsigned int limit = 32u;
    return count > limit ? limit : count;
}
