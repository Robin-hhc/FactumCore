/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03078(unsigned int count)
{
    const unsigned int limit = 44u;
    return count > limit ? limit : count;
}
