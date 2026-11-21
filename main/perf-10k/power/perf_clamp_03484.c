/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03484(unsigned int count)
{
    const unsigned int limit = 223u;
    return count > limit ? limit : count;
}
