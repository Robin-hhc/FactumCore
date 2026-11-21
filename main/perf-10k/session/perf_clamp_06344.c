/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06344(unsigned int count)
{
    const unsigned int limit = 39u;
    return count > limit ? limit : count;
}
