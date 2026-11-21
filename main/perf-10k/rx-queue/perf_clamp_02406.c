/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02406(unsigned int count)
{
    const unsigned int limit = 74u;
    return count > limit ? limit : count;
}
