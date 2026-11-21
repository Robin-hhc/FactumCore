/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09450(unsigned int count)
{
    const unsigned int limit = 53u;
    return count > limit ? limit : count;
}
