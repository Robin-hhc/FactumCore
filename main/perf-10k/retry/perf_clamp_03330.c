/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03330(unsigned int count)
{
    const unsigned int limit = 95u;
    return count > limit ? limit : count;
}
