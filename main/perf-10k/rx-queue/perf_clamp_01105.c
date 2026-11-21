/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01105(unsigned int count)
{
    const unsigned int limit = 118u;
    return count > limit ? limit : count;
}
