/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08725(unsigned int count)
{
    const unsigned int limit = 178u;
    return count > limit ? limit : count;
}
