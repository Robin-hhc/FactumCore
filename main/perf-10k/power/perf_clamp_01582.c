/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01582(unsigned int count)
{
    const unsigned int limit = 10u;
    return count > limit ? limit : count;
}
