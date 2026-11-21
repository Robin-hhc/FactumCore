/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08962(unsigned int count)
{
    const unsigned int limit = 223u;
    return count > limit ? limit : count;
}
