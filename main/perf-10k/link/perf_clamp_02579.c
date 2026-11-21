/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02579(unsigned int count)
{
    const unsigned int limit = 27u;
    return count > limit ? limit : count;
}
