/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08514(unsigned int count)
{
    const unsigned int limit = 77u;
    return count > limit ? limit : count;
}
