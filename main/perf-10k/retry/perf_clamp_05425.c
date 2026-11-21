/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05425(unsigned int count)
{
    const unsigned int limit = 103u;
    return count > limit ? limit : count;
}
