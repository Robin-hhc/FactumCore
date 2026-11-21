/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06305(unsigned int count)
{
    const unsigned int limit = 123u;
    return count > limit ? limit : count;
}
