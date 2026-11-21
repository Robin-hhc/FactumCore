/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01181(unsigned int count)
{
    const unsigned int limit = 165u;
    return count > limit ? limit : count;
}
