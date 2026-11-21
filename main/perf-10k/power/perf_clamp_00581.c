/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00581(unsigned int count)
{
    const unsigned int limit = 174u;
    return count > limit ? limit : count;
}
