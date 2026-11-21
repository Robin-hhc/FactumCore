/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06250(unsigned int count)
{
    const unsigned int limit = 184u;
    return count > limit ? limit : count;
}
