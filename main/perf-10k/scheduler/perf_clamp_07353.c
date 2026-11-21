/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07353(unsigned int count)
{
    const unsigned int limit = 11u;
    return count > limit ? limit : count;
}
