/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07861(unsigned int count)
{
    const unsigned int limit = 181u;
    return count > limit ? limit : count;
}
