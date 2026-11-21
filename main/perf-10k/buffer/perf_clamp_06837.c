/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06837(unsigned int count)
{
    const unsigned int limit = 203u;
    return count > limit ? limit : count;
}
