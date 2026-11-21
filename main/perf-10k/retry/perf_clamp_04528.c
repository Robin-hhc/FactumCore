/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04528(unsigned int count)
{
    const unsigned int limit = 43u;
    return count > limit ? limit : count;
}
