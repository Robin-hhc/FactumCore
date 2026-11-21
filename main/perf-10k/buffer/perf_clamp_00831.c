/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00831(unsigned int count)
{
    const unsigned int limit = 191u;
    return count > limit ? limit : count;
}
