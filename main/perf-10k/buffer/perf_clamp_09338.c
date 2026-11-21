/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09338(unsigned int count)
{
    const unsigned int limit = 141u;
    return count > limit ? limit : count;
}
