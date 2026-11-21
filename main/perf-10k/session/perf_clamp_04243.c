/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04243(unsigned int count)
{
    const unsigned int limit = 178u;
    return count > limit ? limit : count;
}
