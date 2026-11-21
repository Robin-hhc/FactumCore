/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01824(unsigned int count)
{
    const unsigned int limit = 140u;
    return count > limit ? limit : count;
}
