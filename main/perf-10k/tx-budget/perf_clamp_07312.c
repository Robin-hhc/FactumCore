/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07312(unsigned int count)
{
    const unsigned int limit = 61u;
    return count > limit ? limit : count;
}
