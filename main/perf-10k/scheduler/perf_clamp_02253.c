/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02253(unsigned int count)
{
    const unsigned int limit = 212u;
    return count > limit ? limit : count;
}
