/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06635(unsigned int count)
{
    const unsigned int limit = 255u;
    return count > limit ? limit : count;
}
