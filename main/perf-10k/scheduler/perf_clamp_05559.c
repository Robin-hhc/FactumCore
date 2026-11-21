/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05559(unsigned int count)
{
    const unsigned int limit = 140u;
    return count > limit ? limit : count;
}
