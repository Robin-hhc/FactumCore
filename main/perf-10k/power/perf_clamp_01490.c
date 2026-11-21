/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01490(unsigned int count)
{
    const unsigned int limit = 189u;
    return count > limit ? limit : count;
}
