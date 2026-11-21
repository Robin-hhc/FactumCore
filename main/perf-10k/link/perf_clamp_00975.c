/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00975(unsigned int count)
{
    const unsigned int limit = 149u;
    return count > limit ? limit : count;
}
