/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08167(unsigned int count)
{
    const unsigned int limit = 154u;
    return count > limit ? limit : count;
}
