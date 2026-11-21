/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02582(unsigned int count)
{
    const unsigned int limit = 78u;
    return count > limit ? limit : count;
}
