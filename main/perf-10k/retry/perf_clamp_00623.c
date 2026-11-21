/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00623(unsigned int count)
{
    const unsigned int limit = 141u;
    return count > limit ? limit : count;
}
