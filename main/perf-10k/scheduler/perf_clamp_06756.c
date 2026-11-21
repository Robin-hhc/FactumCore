/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06756(unsigned int count)
{
    const unsigned int limit = 71u;
    return count > limit ? limit : count;
}
