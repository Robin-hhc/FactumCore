/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02432(unsigned int count)
{
    const unsigned int limit = 18u;
    return count > limit ? limit : count;
}
