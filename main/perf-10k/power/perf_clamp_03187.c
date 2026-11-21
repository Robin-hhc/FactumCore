/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03187(unsigned int count)
{
    const unsigned int limit = 154u;
    return count > limit ? limit : count;
}
