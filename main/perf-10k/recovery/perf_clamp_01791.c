/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01791(unsigned int count)
{
    const unsigned int limit = 77u;
    return count > limit ? limit : count;
}
