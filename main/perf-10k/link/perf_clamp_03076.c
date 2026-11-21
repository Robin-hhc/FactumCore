/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03076(unsigned int count)
{
    const unsigned int limit = 10u;
    return count > limit ? limit : count;
}
