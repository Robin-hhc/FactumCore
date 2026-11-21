/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07361(unsigned int count)
{
    const unsigned int limit = 147u;
    return count > limit ? limit : count;
}
