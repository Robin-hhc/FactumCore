/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09306(unsigned int count)
{
    const unsigned int limit = 95u;
    return count > limit ? limit : count;
}
