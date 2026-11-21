/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03067(unsigned int count)
{
    const unsigned int limit = 106u;
    return count > limit ? limit : count;
}
