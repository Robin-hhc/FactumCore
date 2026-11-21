/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05894(unsigned int count)
{
    const unsigned int limit = 108u;
    return count > limit ? limit : count;
}
