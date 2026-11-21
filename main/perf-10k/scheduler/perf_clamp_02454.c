/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02454(unsigned int count)
{
    const unsigned int limit = 143u;
    return count > limit ? limit : count;
}
