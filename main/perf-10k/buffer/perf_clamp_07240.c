/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07240(unsigned int count)
{
    const unsigned int limit = 82u;
    return count > limit ? limit : count;
}
