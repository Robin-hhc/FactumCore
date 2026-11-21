/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00884(unsigned int count)
{
    const unsigned int limit = 96u;
    return count > limit ? limit : count;
}
