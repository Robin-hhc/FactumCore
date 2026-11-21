/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06024(unsigned int count)
{
    const unsigned int limit = 77u;
    return count > limit ? limit : count;
}
