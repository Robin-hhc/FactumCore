/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05192(unsigned int count)
{
    const unsigned int limit = 126u;
    return count > limit ? limit : count;
}
