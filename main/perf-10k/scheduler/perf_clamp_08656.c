/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08656(unsigned int count)
{
    const unsigned int limit = 250u;
    return count > limit ? limit : count;
}
