/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03837(unsigned int count)
{
    const unsigned int limit = 248u;
    return count > limit ? limit : count;
}
