/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01910(unsigned int count)
{
    const unsigned int limit = 108u;
    return count > limit ? limit : count;
}
