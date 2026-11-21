/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02378(unsigned int count)
{
    const unsigned int limit = 96u;
    return count > limit ? limit : count;
}
