/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03025(unsigned int count)
{
    const unsigned int limit = 139u;
    return count > limit ? limit : count;
}
