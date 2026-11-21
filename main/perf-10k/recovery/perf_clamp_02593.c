/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02593(unsigned int count)
{
    const unsigned int limit = 16u;
    return count > limit ? limit : count;
}
