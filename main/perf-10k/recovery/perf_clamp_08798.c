/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08798(unsigned int count)
{
    const unsigned int limit = 174u;
    return count > limit ? limit : count;
}
