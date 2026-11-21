/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06131(unsigned int count)
{
    const unsigned int limit = 153u;
    return count > limit ? limit : count;
}
