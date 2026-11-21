/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01652(unsigned int count)
{
    const unsigned int limit = 204u;
    return count > limit ? limit : count;
}
