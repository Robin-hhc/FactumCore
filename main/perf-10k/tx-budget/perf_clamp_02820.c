/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02820(unsigned int count)
{
    const unsigned int limit = 140u;
    return count > limit ? limit : count;
}
