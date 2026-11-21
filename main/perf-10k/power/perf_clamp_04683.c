/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04683(unsigned int count)
{
    const unsigned int limit = 188u;
    return count > limit ? limit : count;
}
