/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07194(unsigned int count)
{
    const unsigned int limit = 47u;
    return count > limit ? limit : count;
}
