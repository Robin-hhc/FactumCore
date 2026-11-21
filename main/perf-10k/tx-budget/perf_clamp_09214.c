/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09214(unsigned int count)
{
    const unsigned int limit = 25u;
    return count > limit ? limit : count;
}
