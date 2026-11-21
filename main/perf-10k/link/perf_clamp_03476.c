/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03476(unsigned int count)
{
    const unsigned int limit = 87u;
    return count > limit ? limit : count;
}
