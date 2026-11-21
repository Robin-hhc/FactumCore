/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03145(unsigned int count)
{
    const unsigned int limit = 187u;
    return count > limit ? limit : count;
}
