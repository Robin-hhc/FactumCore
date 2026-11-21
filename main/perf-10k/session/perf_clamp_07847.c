/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07847(unsigned int count)
{
    const unsigned int limit = 192u;
    return count > limit ? limit : count;
}
