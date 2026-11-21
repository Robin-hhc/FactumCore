/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08936(unsigned int count)
{
    const unsigned int limit = 30u;
    return count > limit ? limit : count;
}
