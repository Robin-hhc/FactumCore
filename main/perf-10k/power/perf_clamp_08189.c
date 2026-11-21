/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08189(unsigned int count)
{
    const unsigned int limit = 30u;
    return count > limit ? limit : count;
}
