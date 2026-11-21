/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02908(unsigned int count)
{
    const unsigned int limit = 142u;
    return count > limit ? limit : count;
}
