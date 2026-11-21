/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01750(unsigned int count)
{
    const unsigned int limit = 127u;
    return count > limit ? limit : count;
}
