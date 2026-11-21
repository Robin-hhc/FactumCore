/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02013(unsigned int count)
{
    const unsigned int limit = 116u;
    return count > limit ? limit : count;
}
