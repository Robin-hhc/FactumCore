/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09714(unsigned int count)
{
    const unsigned int limit = 59u;
    return count > limit ? limit : count;
}
