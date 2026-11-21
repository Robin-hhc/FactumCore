/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08135(unsigned int count)
{
    const unsigned int limit = 108u;
    return count > limit ? limit : count;
}
