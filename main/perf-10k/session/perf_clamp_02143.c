/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02143(unsigned int count)
{
    const unsigned int limit = 85u;
    return count > limit ? limit : count;
}
