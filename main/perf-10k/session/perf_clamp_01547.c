/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01547(unsigned int count)
{
    const unsigned int limit = 162u;
    return count > limit ? limit : count;
}
