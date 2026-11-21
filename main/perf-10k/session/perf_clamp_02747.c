/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02747(unsigned int count)
{
    const unsigned int limit = 144u;
    return count > limit ? limit : count;
}
