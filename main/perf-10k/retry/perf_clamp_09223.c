/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09223(unsigned int count)
{
    const unsigned int limit = 178u;
    return count > limit ? limit : count;
}
