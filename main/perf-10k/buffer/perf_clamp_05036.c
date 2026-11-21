/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05036(unsigned int count)
{
    const unsigned int limit = 213u;
    return count > limit ? limit : count;
}
