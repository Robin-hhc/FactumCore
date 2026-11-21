/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06008(unsigned int count)
{
    const unsigned int limit = 54u;
    return count > limit ? limit : count;
}
