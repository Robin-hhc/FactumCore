/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09666(unsigned int count)
{
    const unsigned int limit = 239u;
    return count > limit ? limit : count;
}
