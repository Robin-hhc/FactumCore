/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02101(unsigned int count)
{
    const unsigned int limit = 118u;
    return count > limit ? limit : count;
}
