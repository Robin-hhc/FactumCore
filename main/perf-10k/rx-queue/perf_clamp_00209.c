/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00209(unsigned int count)
{
    const unsigned int limit = 75u;
    return count > limit ? limit : count;
}
