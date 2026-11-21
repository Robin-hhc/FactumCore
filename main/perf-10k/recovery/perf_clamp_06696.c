/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06696(unsigned int count)
{
    const unsigned int limit = 47u;
    return count > limit ? limit : count;
}
