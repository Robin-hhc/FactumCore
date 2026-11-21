/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04105(unsigned int count)
{
    const unsigned int limit = 73u;
    return count > limit ? limit : count;
}
