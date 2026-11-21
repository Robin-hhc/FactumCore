/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03456(unsigned int count)
{
    const unsigned int limit = 245u;
    return count > limit ? limit : count;
}
