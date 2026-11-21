/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06648(unsigned int count)
{
    const unsigned int limit = 227u;
    return count > limit ? limit : count;
}
