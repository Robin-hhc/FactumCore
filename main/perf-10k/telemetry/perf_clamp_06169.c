/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06169(unsigned int count)
{
    const unsigned int limit = 52u;
    return count > limit ? limit : count;
}
