/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08882(unsigned int count)
{
    const unsigned int limit = 108u;
    return count > limit ? limit : count;
}
