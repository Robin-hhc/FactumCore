/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01382(unsigned int count)
{
    const unsigned int limit = 96u;
    return count > limit ? limit : count;
}
