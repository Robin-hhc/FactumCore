/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08673(unsigned int count)
{
    const unsigned int limit = 41u;
    return count > limit ? limit : count;
}
