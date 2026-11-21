/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00023(unsigned int count)
{
    const unsigned int limit = 150u;
    return count > limit ? limit : count;
}
