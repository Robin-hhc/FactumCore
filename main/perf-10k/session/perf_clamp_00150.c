/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00150(unsigned int count)
{
    const unsigned int limit = 68u;
    return count > limit ? limit : count;
}
