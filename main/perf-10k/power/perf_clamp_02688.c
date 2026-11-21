/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02688(unsigned int count)
{
    const unsigned int limit = 137u;
    return count > limit ? limit : count;
}
