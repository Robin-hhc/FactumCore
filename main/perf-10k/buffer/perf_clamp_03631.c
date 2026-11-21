/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03631(unsigned int count)
{
    const unsigned int limit = 232u;
    return count > limit ? limit : count;
}
