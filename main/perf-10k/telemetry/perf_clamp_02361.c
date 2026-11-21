/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02361(unsigned int count)
{
    const unsigned int limit = 56u;
    return count > limit ? limit : count;
}
