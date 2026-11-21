/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09523(unsigned int count)
{
    const unsigned int limit = 49u;
    return count > limit ? limit : count;
}
