/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09078(unsigned int count)
{
    const unsigned int limit = 203u;
    return count > limit ? limit : count;
}
