/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04312(unsigned int count)
{
    const unsigned int limit = 106u;
    return count > limit ? limit : count;
}
