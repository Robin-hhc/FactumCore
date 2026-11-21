/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06093(unsigned int count)
{
    const unsigned int limit = 254u;
    return count > limit ? limit : count;
}
