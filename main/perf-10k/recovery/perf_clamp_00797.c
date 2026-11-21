/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00797(unsigned int count)
{
    const unsigned int limit = 111u;
    return count > limit ? limit : count;
}
