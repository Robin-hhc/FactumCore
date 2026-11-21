/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08086(unsigned int count)
{
    const unsigned int limit = 22u;
    return count > limit ? limit : count;
}
