/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01831(unsigned int count)
{
    const unsigned int limit = 10u;
    return count > limit ? limit : count;
}
