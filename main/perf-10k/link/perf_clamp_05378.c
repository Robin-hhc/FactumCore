/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05378(unsigned int count)
{
    const unsigned int limit = 51u;
    return count > limit ? limit : count;
}
