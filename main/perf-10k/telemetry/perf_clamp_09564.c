/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09564(unsigned int count)
{
    const unsigned int limit = 248u;
    return count > limit ? limit : count;
}
