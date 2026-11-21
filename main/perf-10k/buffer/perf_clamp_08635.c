/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08635(unsigned int count)
{
    const unsigned int limit = 142u;
    return count > limit ? limit : count;
}
