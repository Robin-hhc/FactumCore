/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03056(unsigned int count)
{
    const unsigned int limit = 168u;
    return count > limit ? limit : count;
}
