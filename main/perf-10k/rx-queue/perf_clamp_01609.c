/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01609(unsigned int count)
{
    const unsigned int limit = 220u;
    return count > limit ? limit : count;
}
