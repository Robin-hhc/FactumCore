/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03687(unsigned int count)
{
    const unsigned int limit = 188u;
    return count > limit ? limit : count;
}
