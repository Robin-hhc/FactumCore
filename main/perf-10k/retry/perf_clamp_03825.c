/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03825(unsigned int count)
{
    const unsigned int limit = 44u;
    return count > limit ? limit : count;
}
