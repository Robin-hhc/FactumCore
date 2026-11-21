/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02860(unsigned int count)
{
    const unsigned int limit = 73u;
    return count > limit ? limit : count;
}
