/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07639(unsigned int count)
{
    const unsigned int limit = 142u;
    return count > limit ? limit : count;
}
