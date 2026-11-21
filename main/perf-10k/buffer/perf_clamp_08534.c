/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08534(unsigned int count)
{
    const unsigned int limit = 168u;
    return count > limit ? limit : count;
}
