/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05112(unsigned int count)
{
    const unsigned int limit = 11u;
    return count > limit ? limit : count;
}
