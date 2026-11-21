/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05656(unsigned int count)
{
    const unsigned int limit = 46u;
    return count > limit ? limit : count;
}
