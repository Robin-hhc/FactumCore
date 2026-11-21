/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08301(unsigned int count)
{
    const unsigned int limit = 191u;
    return count > limit ? limit : count;
}
