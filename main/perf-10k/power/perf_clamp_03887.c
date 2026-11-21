/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03887(unsigned int count)
{
    const unsigned int limit = 102u;
    return count > limit ? limit : count;
}
