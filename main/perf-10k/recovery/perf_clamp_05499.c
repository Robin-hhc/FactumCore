/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05499(unsigned int count)
{
    const unsigned int limit = 116u;
    return count > limit ? limit : count;
}
