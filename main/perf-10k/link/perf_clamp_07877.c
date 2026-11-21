/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07877(unsigned int count)
{
    const unsigned int limit = 204u;
    return count > limit ? limit : count;
}
