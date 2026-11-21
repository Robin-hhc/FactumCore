/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03361(unsigned int count)
{
    const unsigned int limit = 124u;
    return count > limit ? limit : count;
}
