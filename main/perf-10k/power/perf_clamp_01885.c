/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01885(unsigned int count)
{
    const unsigned int limit = 181u;
    return count > limit ? limit : count;
}
