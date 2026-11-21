/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04884(unsigned int count)
{
    const unsigned int limit = 119u;
    return count > limit ? limit : count;
}
