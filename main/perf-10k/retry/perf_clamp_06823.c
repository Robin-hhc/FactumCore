/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06823(unsigned int count)
{
    const unsigned int limit = 214u;
    return count > limit ? limit : count;
}
