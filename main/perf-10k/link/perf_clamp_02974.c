/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02974(unsigned int count)
{
    const unsigned int limit = 19u;
    return count > limit ? limit : count;
}
