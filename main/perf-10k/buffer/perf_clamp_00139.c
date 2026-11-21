/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00139(unsigned int count)
{
    const unsigned int limit = 130u;
    return count > limit ? limit : count;
}
