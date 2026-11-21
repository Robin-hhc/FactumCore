/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08329(unsigned int count)
{
    const unsigned int limit = 169u;
    return count > limit ? limit : count;
}
