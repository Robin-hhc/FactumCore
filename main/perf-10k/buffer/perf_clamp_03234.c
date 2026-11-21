/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03234(unsigned int count)
{
    const unsigned int limit = 206u;
    return count > limit ? limit : count;
}
