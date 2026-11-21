/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07392(unsigned int count)
{
    const unsigned int limit = 176u;
    return count > limit ? limit : count;
}
