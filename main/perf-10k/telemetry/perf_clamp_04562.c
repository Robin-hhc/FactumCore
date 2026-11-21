/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04562(unsigned int count)
{
    const unsigned int limit = 123u;
    return count > limit ? limit : count;
}
