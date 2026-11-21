/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03168(unsigned int count)
{
    const unsigned int limit = 80u;
    return count > limit ? limit : count;
}
