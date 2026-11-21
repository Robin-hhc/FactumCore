/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06686(unsigned int count)
{
    const unsigned int limit = 126u;
    return count > limit ? limit : count;
}
