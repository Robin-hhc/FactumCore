/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00895(unsigned int count)
{
    const unsigned int limit = 34u;
    return count > limit ? limit : count;
}
