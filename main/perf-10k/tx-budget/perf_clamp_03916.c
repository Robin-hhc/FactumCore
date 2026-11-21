/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03916(unsigned int count)
{
    const unsigned int limit = 97u;
    return count > limit ? limit : count;
}
